import logging
import os
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from attrs_configs import AttrsModel, AttrsNested, AttrsNestedRestraint
from configs import (ConstrinedEnv, FurtherEnv2, NestedDefaultedEnv,
                     NestedMissingEnv, OptionalFlagEnv, SimpleEnv)
from pydantic_configs import PydModel, PydNested, PydNestedRestraint

from mininterface import Mininterface, TextInterface, run, validators
from mininterface.auxiliary import flatten
from mininterface.FormDict import dataclass_to_formdict, formdict_repr
from mininterface.FormField import FormField
from mininterface.Mininterface import Cancelled

SYS_ARGV = None  # To be redirected


class TestAbstract(TestCase):
    def setUp(self):
        global SYS_ARGV
        SYS_ARGV = sys.argv
        self.sys()

    def tearDown(self):
        global SYS_ARGV
        sys.argv = SYS_ARGV

    @classmethod
    def sys(cls, *args):
        sys.argv = ["running-tests", *args]


class TestCli(TestAbstract):
    def test_basic(self):
        def go(*_args) -> SimpleEnv:
            self.sys(*_args)
            return run(SimpleEnv, interface=Mininterface, prog="My application").env

        self.assertEqual(4, go().important_number)
        self.assertEqual(False, go().test)
        self.assertEqual(5, go("--important-number", "5").important_number)
        self.assertEqual(6, go("--important-number=6").important_number)
        self.assertEqual(7, go("--important_number=7").important_number)

        self.sys("--important_number='8'")
        self.assertRaises(SystemExit, lambda: run(SimpleEnv, interface=Mininterface, prog="My application"))

    def test_cli_complex(self):
        def go(*_args) -> NestedDefaultedEnv:
            self.sys(*_args)
            return run(NestedDefaultedEnv, interface=Mininterface, prog="My application").env

        self.assertEqual("example.org", go().further.host)
        self.assertEqual("example.com", go("--further.host=example.com").further.host)
        self.assertEqual("'example.net'", go("--further.host='example.net'").further.host)
        self.assertEqual("example.org", go("--further.host", 'example.org').further.host)
        self.assertEqual("example org", go("--further.host", 'example org').further.host)

        def go2(*_args) -> NestedMissingEnv:
            self.sys(*_args)
            return run(NestedMissingEnv, interface=Mininterface, prog="My application").env
        self.assertEqual("example.org", go2("--further.token=1").further.host)
        self.assertEqual("example.com", go2("--further.token=1", "--further.host=example.com").further.host)
        self.assertEqual("'example.net'", go2("--further.token=1", "--further.host='example.net'").further.host)
        self.sys("--further.host='example.net'")
        self.assertRaises(SystemExit, lambda: run(SimpleEnv, interface=Mininterface, prog="My application"))


class TestInteface(TestAbstract):
    def test_ask(self):
        m0 = run(NestedDefaultedEnv, interface=Mininterface, prog="My application")
        self.assertEqual(0, m0.ask_number("Test input"))

        m1: TextInterface = run(NestedDefaultedEnv, interface=TextInterface, prog="My application")
        with patch('builtins.input', return_value=5):
            self.assertEqual(5, m1.ask_number("Number"))
        with patch('builtins.input', side_effect=["invalid", 1]):
            self.assertEqual(1, m1.ask_number("Number"))
        with patch('builtins.input', side_effect=["invalid", EOFError]):
            with self.assertRaises(Cancelled):
                self.assertEqual(1, m1.ask_number("Number"))

        with patch('builtins.input', side_effect=["", "", "y", "Y", "n", "n", "N", "y", "hello"]):
            self.assertTrue(m1.is_yes(""))
            self.assertTrue(m1.is_no(""))

            self.assertTrue(m1.is_yes(""))
            self.assertTrue(m1.is_yes(""))
            self.assertFalse(m1.is_yes(""))

            self.assertTrue(m1.is_no(""))
            self.assertTrue(m1.is_no(""))
            self.assertFalse(m1.is_no(""))

            self.assertEqual("hello", m1.ask(""))

    def test_ask_form(self):
        m = TextInterface()
        dict1 = {"my label": FormField(True, "my description"), "nested": {"inner": "text"}}
        with patch('builtins.input', side_effect=["v['nested']['inner'] = 'another'", "c"]):
            m.form(dict1)
        self.assertEqual({"my label": FormField(True, "my description"), "nested": {"inner": "another"}}, dict1)

        # Empty form invokes editing self.env, which is empty
        with patch('builtins.input', side_effect=["c"]):
            self.assertEqual(SimpleNamespace(), m.form())

        # Empty form invokes editing self.env, which contains a dataclass
        m2 = run(SimpleEnv, interface=TextInterface, prog="My application")
        self.assertFalse(m2.env.test)
        with patch('builtins.input', side_effect=["v.test = True", "c"]):
            self.assertEqual(m2.env, m2.form())
            self.assertTrue(m2.env.test)


class TestConversion(TestAbstract):
    def test_normalize_types(self):
        """ Conversion str("") to None and back.
        When using GUI interface, we input an empty string and that should mean None
        for annotation `int | None`.
        """
        origin = {'': {'test': FormField(False, 'Testing flag ', annotation=None),
                       'numb': FormField(4, 'A number', annotation=None),
                       'severity': FormField('', 'integer or none ', annotation=int | None),
                       'msg': FormField('', 'string or none', annotation=str | None)}}
        data = {'': {'test': False, 'numb': 4, 'severity': 'fd', 'msg': ''}}

        self.assertFalse(FormField.submit(origin, data))
        data = {'': {'test': False, 'numb': 4, 'severity': '1', 'msg': ''}}
        self.assertTrue(FormField.submit(origin, data))
        data = {'': {'test': False, 'numb': 4, 'severity': '', 'msg': ''}}
        self.assertTrue(FormField.submit(origin, data))
        data = {'': {'test': False, 'numb': 4, 'severity': '1', 'msg': 'Text'}}
        self.assertTrue(FormField.submit(origin, data))

        # check value is kept if revision needed
        self.assertEqual(False, origin[""]["test"].val)
        data = {'': {'test': True, 'numb': 100, 'severity': '1', 'msg': 1}}  # ui put a wrong 'msg' type
        self.assertFalse(FormField.submit(origin, data))
        self.assertEqual(True, origin[""]["test"].val)
        self.assertEqual(100, origin[""]["numb"].val)

        # Check flat FormDict
        origin = {'test': FormField(False, 'Testing flag ', annotation=None),
                  'severity': FormField('', 'integer or none ', annotation=int | None),
                  'nested': {'test2': FormField(4, '')}}
        #   'nested': {'test2': 4}} TODO, allow combined FormDict
        data = {'test': True, 'severity': "", 'nested': {'test2': 8}}
        self.assertTrue(FormField.submit(origin, data))
        data = {'test': True, 'severity': "str", 'nested': {'test2': 8}}
        self.assertFalse(FormField.submit(origin, data))

    def test_non_scalar(self):
        ff = FormField(Path("/tmp"), '')
        origin = {'': {'path': ff}}
        data = {'': {'path': "/usr"}}  # the input '/usr' is a str
        self.assertTrue(FormField.submit(origin, data))
        self.assertEqual(Path("/usr"), ff.val)  # the output is still a Path

    def test_validation(self):
        def validate(ff: FormField):
            val = ff.val
            if 10 < val < 20:
                return "Number must be between 0 ... 10 or 20 ... 100", 20
            if val < 0:
                return False, 30
            if val > 100:
                return "Too high"
            return True

        ff = FormField(100, 'Testing flag', validation=validate)
        origin = {'': {'number': ff}}
        # validation passes
        self.assertTrue(FormField.submit(origin, {'': {'number': 100}}))
        self.assertIsNone(ff.error_text)
        # validation fail, value set by validion
        self.assertFalse(FormField.submit(origin, {'': {'number': 15}}))
        self.assertEqual("Number must be between 0 ... 10 or 20 ... 100", ff.error_text)
        self.assertEqual(20, ff.val)  # value set by validation
        # validation passes again, error text restored
        self.assertTrue(FormField.submit(origin, {'': {'number': 5}}))
        self.assertIsNone(ff.error_text)
        # validation fails, default error text
        self.assertFalse(FormField.submit(origin, {'': {'number': -5}}))
        self.assertEqual("Validation fail", ff.error_text)  # default error text
        self.assertEqual(30, ff.val)
        # validation fails, value not set by validation
        self.assertFalse(FormField.submit(origin, {'': {'number': 101}}))
        self.assertEqual("Too high", ff.error_text)
        self.assertEqual(30, ff.val)

    def test_env_instance_dict_conversion(self):
        m: TextInterface = run(OptionalFlagEnv, interface=TextInterface, prog="My application")
        env1: OptionalFlagEnv = m.env

        self.assertIsNone(env1.severity)

        fd = dataclass_to_formdict(env1, m._descriptions)
        ui = formdict_repr(fd)
        self.assertEqual({'': {'severity': '', 'msg': '', 'msg2': 'Default text'},
                          'further': {'deep': {'flag': False}, 'numb': 0}}, ui)
        self.assertIsNone(env1.severity)

        # do the same as if the tkinter_form was just submitted without any changes
        FormField.submit_values(zip(flatten(fd), flatten(ui)))
        self.assertIsNone(env1.severity)

        # changes in the UI should not directly affect the original
        ui[""]["msg2"] = "Another"
        ui[""]["severity"] = 5
        ui["further"]["deep"]["flag"] = True
        self.assertEqual("Default text", env1.msg2)

        # on UI submit, the original is affected
        FormField.submit_values(zip(flatten(fd), flatten(ui)))
        self.assertEqual("Another", env1.msg2)
        self.assertEqual(5, env1.severity)
        self.assertTrue(env1.further.deep.flag)

        # Another UI changes, makes None from an int
        ui[""]["severity"] = ""  # UI is not able to write None, it does an empty string instead
        FormField.submit_values(zip(flatten(fd), flatten(ui)))
        self.assertIsNone(env1.severity)


class TestRun(TestAbstract):
    def test_run_ask_empty(self):
        with patch('sys.stdout', new_callable=StringIO) as stdout:
            run(SimpleEnv, True, interface=Mininterface)
            self.assertEqual("Asking the form SimpleEnv(test=False, important_number=4)", stdout.getvalue().strip())
        with patch('sys.stdout', new_callable=StringIO) as stdout:
            run(SimpleEnv, interface=Mininterface)
            self.assertEqual("", stdout.getvalue().strip())

    def test_run_ask_for_missing(self):
        form = """Asking the form {'token': FormField(val='', description='', annotation=<class 'str'>, name='token', validation=not_empty, choices=None)}"""
        # Ask for missing, no interference with ask_on_empty_cli
        with patch('sys.stdout', new_callable=StringIO) as stdout:
            run(FurtherEnv2, True, interface=Mininterface)
            self.assertEqual(form, stdout.getvalue().strip())
        with patch('sys.stdout', new_callable=StringIO) as stdout:
            run(FurtherEnv2, False, interface=Mininterface)
            self.assertEqual(form, stdout.getvalue().strip())
        # Ask for missing does not happen, CLI fails
        with self.assertRaises(SystemExit):
            run(FurtherEnv2, True, ask_for_missing=False, interface=Mininterface)

        # No missing field
        self.sys("--token", "1")
        with patch('sys.stdout', new_callable=StringIO) as stdout:
            run(FurtherEnv2, True, ask_for_missing=True, interface=Mininterface)
            self.assertEqual("", stdout.getvalue().strip())
        with patch('sys.stdout', new_callable=StringIO) as stdout:
            run(FurtherEnv2, True, ask_for_missing=False, interface=Mininterface)
            self.assertEqual("", stdout.getvalue().strip())

    def test_run_config_file(self):
        os.chdir("tests")
        sys.argv = ["SimpleEnv.py"]
        self.assertEqual(10, run(SimpleEnv, config_file=True, interface=Mininterface).env.important_number)
        self.assertEqual(4, run(SimpleEnv, config_file=False, interface=Mininterface).env.important_number)
        self.assertEqual(20, run(SimpleEnv, config_file="SimpleEnv2.yaml", interface=Mininterface).env.important_number)
        self.assertEqual(20, run(SimpleEnv, config_file=Path("SimpleEnv2.yaml"),
                         interface=Mininterface).env.important_number)
        self.assertEqual(4, run(SimpleEnv, config_file=Path("empty.yaml"), interface=Mininterface).env.important_number)
        with self.assertRaises(FileNotFoundError):
            run(SimpleEnv, config_file=Path("not-exists.yaml"), interface=Mininterface)


class TestValidators(TestAbstract):
    def test_not_empty(self):
        f = FormField("", validation=validators.not_empty)
        self.assertFalse(f.update(""))
        self.assertTrue(f.update("1"))


class TestLog(TestAbstract):
    @staticmethod
    def log():
        run(SimpleEnv, interface=Mininterface)
        logger = logging.getLogger(__name__)
        logger.debug("debug level")
        logger.info("info level")
        logger.warning("warning level")
        logger.error("error level")

    @patch('logging.basicConfig')
    def test_run_verbosity0(self, mock_basicConfig):
        self.sys("-v")
        with self.assertRaises(SystemExit):
            run(SimpleEnv, add_verbosity=False, interface=Mininterface)
        mock_basicConfig.assert_not_called()

    @patch('logging.basicConfig')
    def test_run_verbosity1(self, mock_basicConfig):
        self.log()
        mock_basicConfig.assert_not_called()

    @patch('logging.basicConfig')
    def test_run_verbosity2(self, mock_basicConfig):
        self.sys("-v")
        self.log()
        mock_basicConfig.assert_called_once_with(level=logging.INFO, format='%(levelname)s - %(message)s')

    @patch('logging.basicConfig')
    def test_run_verbosity2b(self, mock_basicConfig):
        self.sys("--verbose")
        self.log()
        mock_basicConfig.assert_called_once_with(level=logging.INFO, format='%(levelname)s - %(message)s')

    @patch('logging.basicConfig')
    def test_run_verbosity3(self, mock_basicConfig):
        self.sys("-vv")
        self.log()
        mock_basicConfig.assert_called_once_with(level=logging.DEBUG, format='%(levelname)s - %(message)s')


class TestPydanticIntegration(TestAbstract):
    def test_basic(self):
        m = run(PydModel, interface=Mininterface)
        self.assertEqual("hello", m.env.name)

    def test_nested(self):
        m = run(PydNested, interface=Mininterface)
        self.assertEqual(-100, m.env.number)

        self.sys("--number", "-200")
        m = run(PydNested, interface=Mininterface)
        self.assertEqual(-200, m.env.number)
        self.assertEqual(4, m.env.inner.number)

    def test_config(self):
        m = run(PydNested, config_file="tests/pydantic.yaml", interface=Mininterface)
        self.assertEqual(100, m.env.number)
        self.assertEqual(0, m.env.inner.number)
        self.assertEqual("hello", m.env.inner.text)

    def test_nested_restraint(self):
        m = run(PydNestedRestraint, interface=Mininterface)
        self.assertEqual("hello", m.env.inner.name)

        f = dataclass_to_formdict(m.env, m._descriptions)["inner"]["name"]
        self.assertTrue(f.update("short"))
        self.assertEqual("Restrained name ", f.description)
        self.assertFalse(f.update("long words"))
        self.assertEqual("String should have at most 5 characters Restrained name ", f.description)
        self.assertTrue(f.update(""))
        self.assertEqual("Restrained name ", f.description)

    # NOTE
    # def test_run_ask_for_missing(self):
    #   Might be a mess. Seems that missing fields are working better
    #   when nested than directly.

class TestAttrsIntegration(TestAbstract):
    def test_basic(self):
        m = run(AttrsModel, interface=Mininterface)
        self.assertEqual("hello", m.env.name)

    def test_nested(self):
        m = run(AttrsNested, interface=Mininterface)
        self.assertEqual(-100, m.env.number)

        self.sys("--number", "-200")
        m = run(AttrsNested, interface=Mininterface)
        self.assertEqual(-200, m.env.number)
        self.assertEqual(4, m.env.inner.number)

    def test_config(self):
        m = run(AttrsNested, config_file="tests/pydantic.yaml", interface=Mininterface)
        self.assertEqual(100, m.env.number)
        self.assertEqual(0, m.env.inner.number)
        self.assertEqual("hello", m.env.inner.text)

    def test_nested_restraint(self):
        m = run(AttrsNestedRestraint, interface=Mininterface)
        self.assertEqual("hello", m.env.inner.name)

        f = dataclass_to_formdict(m.env, m._descriptions)["inner"]["name"]
        self.assertTrue(f.update("short"))
        self.assertEqual("Restrained name ", f.description)
        self.assertFalse(f.update("long words"))
        self.assertEqual("Length of 'check' must be <= 5: 10 Restrained name ", f.description)
        self.assertTrue(f.update(""))
        self.assertEqual("Restrained name ", f.description)

class TestAnnotated(TestAbstract):
    def test_annotated(self):
        m = run(ConstrinedEnv)
        d = dataclass_to_formdict(m.env, m._descriptions)
        self.assertFalse(d[""]["test"].update(""))
        self.assertFalse(d[""]["test2"].update(""))
        self.assertTrue(d[""]["test"].update(" "))
        self.assertTrue(d[""]["test2"].update(" "))

if __name__ == '__main__':
    main()
