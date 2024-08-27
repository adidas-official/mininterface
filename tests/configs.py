from dataclasses import dataclass

@dataclass
class SimpleEnv:
    """Set of options."""
    test: bool = False
    """My testing flag"""
    important_number: int = 4
    """This number is very important"""


@dataclass
class FurtherEnv1:
    token: str = "filled"
    host: str = "example.org"


@dataclass
class NestedDefaultedEnv:
    further: FurtherEnv1


@dataclass
class FurtherEnv2:
    token: str
    host: str = "example.org"

@dataclass
class NestedMissingEnv:
    further: FurtherEnv2


@dataclass
class FurtherEnv4:
    flag: bool = False
@dataclass
class FurtherEnv3:
    deep: FurtherEnv4
    numb: int = 0

@dataclass
class OptionalFlagEnv:
    further: FurtherEnv3
    severity: int | None = None
    """ This number is optional """

    msg: str | None = None
    """ An example message """

    msg2: str | None = "Default text"
    """ Another example message """