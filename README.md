# Custom FLuid flexible declarative Macro Driver
This is a custom macro driver that i wrote fr emulate any form of macros on a screen.
The macro is entirely declarative.

## Manager 🔮
The manager is the main orchestrater of any macro. THe manager starts processes, manages function, handles runtime and registry and initiates cleanup after execution/interuption.
/

### Usage 🎯
The manager reads the structure of execution from the json inside strategies.
Manager calls the abbreviated functions and raleted manager_functions inside the funcitons directory, parses them with its resolver functions, and executes/managers their runtime.

#### Example Json.

```json
{
  "services": [
    "battle"
  ],
  "sequence": [
    {
      "loop": {
        "count": "forever",
        "do": [
          {"click": [434, 865]},
          {"sleep": [0.5]},
          {"click": [434, 865]},
          {"sleep": [0.5]}
        ]
      }
    }

```

## Functions
The functions directory is the major directory, which all the scripts and manager calls to execute functions.
To add upon this repository further, like new features/ execution routes, directly add new functions in the directory inside the corresponding function file.
/
### Variables.py 
Here every variable(mainly for scripts) are defined.
To change parameters inside any script, directly change these parameters inside this file.

### Abbreviations.py
This is the main file, where every tool / quick function receives an abbreviation that the user can use in their json, and the manager can parse to execute it.

#### IF YOU ADD NEW FUNCTIONS / SCRIPTS
Make sure to add the corresponding path of the tool inside abbreviations, and if you are using handlers in your function, add that too.

## Config
