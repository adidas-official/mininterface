## UI Settings

The UI behaviour might be modified via an settings object. This can be passed to the [run][mininterface.run] function or defined through a config file. Settings defined in the config file have bigger priority. Every interface has its own settings object.

## Config file special section
In a YAML config file, use a special section 'mininterface' to set up the UI. For example, this stub will enforce your program to use the Tui interface.

```yaml
mininterface:
    interface: tui
```

## Complete example

Source of `program.py`, we have one single attribute `foo`:

```python
from typing import Annotated
from dataclasses import dataclass
from mininterface import run, Options

@dataclass
class Env:
    foo: Annotated["str", Options("one", "two")] = "one"

m = run(Env)
m.form()
```

Source of `program.yaml` will enforce the comboboxes:

```yaml
number: 5
mininterface:
    gui:
        combobox_since: 1
```

The difference when using such configuration file.

![Configuration not used](asset/configuration-not-used.avif) ![Configuration used](asset/configuration-used.avif)

## The settings object

```python
from mininterface.settings import MininterfaceSettings

opt = MininterfaceSettings()
run(settings=opt)
```


::: mininterface.settings.MininterfaceSettings

## GuiSettings

```python
from mininterface.settings import MininterfaceSettings, GuiSettings

opt = MininterfaceSettings(gui=GuiSettings(combobox_since=1))
run(settings=opt)
```

::: mininterface.settings.GuiSettings