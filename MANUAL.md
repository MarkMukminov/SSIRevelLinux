# Intro

Hello there! This document provides a quick overview of the Revel Coder app, which you can use to edit and deploy RevelCode automation & hardware configurations.

## RevelCode Documentation

Click **Show Docs** button on the bottom left of the screen to launch RevelCode language documentation. Note that you will need to allow popups from the browser to see the documentation.

## Files in the Workspace

There are two primary types of files you'll be working with in this Revel workspace:

- **`.rvl` files:** RevelCode files containing automation logic that you can build and deploy to the runtime instance
- **`.json` files:** runtime configuration files that describe the hardware configuration and which `.rvl` files you want to deploy

## Workflow

1. Create new `.rvl` files or edit existing ones.
2. Create or edit a system configuration directory with a `system.yaml`, identifying which RevelCode file(s) you want to compile for this deployment (see the **Runtime Configuration Guide** below for description of the configuration format).
3. Switch to the RevelDeploy extension view by clicking the Revel icon on the toolbar at the lefthand edge of the window.
   - In the pane that opens on the lefthand side of the window, you should see a list of all configuration files that exist in the workspace at the top section
   - In an expandable section below each configuration entry in this top section, you'll see the `.rvl` files that that configuration will deploy
   - In the bottom section of the pane, you'll see the currently-deployed files; clicking on these files will show you the diff between the deployed version and the version in the workspace
4. Click the build (🛠️) icon next to your configuration file - if any compilation errors occur, they will appear in the Output Pane at the bottom of the window, describing the location and nature of the issues in your `.rvl` files.
5. Resolve the errors that occur during build, if any.
6. Once all compilation errors are resolved, press the deploy (⤼) icon next to your configuration files.
7. If any errors occur during deployment, they should appear in the Output Pane.
8. During runtime, press the `Update Runtime Log` button in the bottom left to check for any runtime errors - plase report any recurring errors to Revel.

# Setting up a Git repo

To track the code in this repo in Git, you'll need to set up a persistent SSH key to use for validation with your Git remote, clone your repo, and set up your git credentials.

## Adding an SSH key

Any new SSH keys need to be placed in the `/home/coder/workspace/coder_workspace/.ssh` directory.

Follow these steps:
1. Create the `.ssh` directory in the default workspace (`/home/coder/workspace/coder_workspace`).
3. Generate a new SSH key by running `ssh-keygen -t ed25519 -C "your_email@example.com" -f /home/coder/workspace/coder_workspace/.ssh/id_ed25519 -N ''`
4. Add the key to the SSH agent by running `ssh-add /home/coder/workspace/coder_workspace/.ssh/id_ed25519`

Great! You're all set - we'll persist this key across future deployments for your continued use.

## Cloning your Repo + Configuring Credentials

Now, copy the public part of your SSH key pair (the contents of the file ending with `.pub`) and add it to your Git remote account (such as [Github](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account) or [Gitlab](https://docs.gitlab.com/user/ssh/#add-an-ssh-key-to-your-gitlab-account)).

Now, you should be able to clone your repo into the workspace using `git clone`.

Once cloned, run the following in the terminal to configure your Git name/email (this is a one-time setup):
1. Change directories to your new repo with `cd <your-git-repo>`
2. Set up your git user name with `git config user.name "Your Name"`
3. Set up your git user email with `git config user.email "your_email@example.com"`

You're ready to rock! You can now use the terminal or the built-in `Source Control` features of Coder to manage your Git account.

## Making Your Git Repo Your Workspace

If you'd like to open your Coder workspace inside your newly added git repo (so that the base of the workspace is the root of the repo), you can use the file menu (under the ≡ button at the top left) to `Open Folder...` and select your repo.

Bookmark the link after opening inside that folder to quickly navigate to this new preferred workspace view.

# Runtime Configuration Guide

This section describes the JSON configuration format for Revel's Runtime Configuration along with all currently supported fields and values.

The root JSON object must contain the following fields:

| Field         | Type   | Required | Description                                             |
| ------------- | ------ | -------- | ------------------------------------------------------- |
| `system_name` | string | ✅       | Name of the system                                      |
| `files`       | array  | ✅       | List of RevelCode files - see **Files**                 |
| `devices`     | array  | ✅       | List of hardware devices to configure - see **Devices** |

---

## Files

The `files` field specifies which RevelCode files should be compiled and executed - this array should contain a list of `.rvl` filepaths relative to this JSON, in the order in which they should be compiled.

Note that the order of files in this array is important - in effect, the `.rvl` files are concatenated in the specified order and then compiled as "one big file." As such, the order of files' appearance in the array will determine execution order of tasks in different files and the relative location between channel/variable declarations in one file and use of that channel/variable in another file.

It is recommended for the first file in the array to contain the definition of the special `CYCLE` variable, which sets the period in seconds at which the code will be executed, and all declarations for hardware channels.

---

## Devices

Each object in the `devices` array must include the `device_type` field - the value of this field determines the other fields that should be populated:

**`type = NISystem`**
| Field | Type | Required | Description |
|---------------|--------|----------|-------------|
| `ip_address` | string | ✅ | The IP address of the cDAQ system |
| `device_name` | string | ✅ | A descriptive + unique device name for the cDAQ system |
| `channels` | string | ✅ | List of channels on this chassis - see **Channel Objects** |

**`type = CompactRIO`**
| Field | Type | Required | Description |
|---------------|--------|----------|-------------|
| `ip_address` | string | ✅ | The IP address of the cRIO system |
| `device_name` | string | ✅ | A descriptive + unique device name for the cRIO system |
| `channels` | string | ✅ | List of channels on this chassis - see **Channel Objects** |

Note: CompactRIO Only supports the following channel types:
- DigitalInput
- DigitalOutput
- AnalogInput
- AnalogOutput
- Thermocouple

**`device_type = Festo`**
| Field | Type | Required | Description |
|---------------|--------|----------|-------------|
| `ip_address` | string | ✅ | The IP address of the Festo system |
| `device_name` | string | ✅ | A descriptive + unique device name for the Festo system |
| `modules` | string | ✅ | List of modules on this chassis - see **Module Objects** |

**`device_type = TDKPowerSupply`**
| Field | Type | Required | Description |
|---------------|--------|----------|-------------|
| `ip_address` | string | ✅ | The IP address of the power supply |
| `device_name` | string | ✅ | A descriptive + unique device name for the power supply |
| `model` | string | ✅ | The model name of the power supply ("z_plus" or "genysys") |
| `ping_enabled` | bool | ❌ | Whether or not `ping` is enabled in the power supply, used to monitor the connection from the runtime to the power supply (default: `true`) |

**`device_type = MicroMotionEthernetIp`**
| Field | Type | Required | Description |
|---------------|--------|----------|-------------|
| `ip_address` | string | ✅ | The IP address of the Micro Motion 5700 flow meter |
| `device_name` | string | ✅ | A descriptive + unique device name for the flow meter |
| `module` | object | ✅ | EIP module configuration - see **EIP Module Objects** |

**`device_type = OPCUADevice`**
| Field | Type | Required | Description |
|---------------|--------|----------|-------------|
| `device_name` | string | ✅ | A descriptive + unique device name for the OPC UA Device |
| `endpoint_url` | string | ✅ | The full endpoint for the ocp tcp connection |
| `inputs` | objects | ❌ | A list of input channels - see **OPCUAChannelConfig** |
| `methods` | objects | ❌ | A list of methods - see **OPCUAMethodConfig** |

---

### OPCUAChannelConfig

| Field | Type | Required | Description |
|---------------|--------|----------|-------------|
| `revel_name` | string | ✅ | The reference designator you want to assign the channel in RevelCode |
| `node_id` | string | ✅ | The node_id for the OPC UA Channel |
| `channel_type` | object | ✅ | What type of channel this is - see **OPCUAChannelType** |

### OPCUAMethodConfig

| Field | Type | Required | Description |
|---------------|--------|----------|-------------|
| `method_name` | string | ✅ | the name of the method |
| `object_id` | string | ✅ | the node_id of the parent object |
| `node_id` | string | ✅ | the node_id of the method |
| `arguments` | objects | ❌ | A list of Argument Channels - see **OPCUAMethodArgument** |

### OPCUAMethodArgument

| Field | Type | Required | Description |
|---------------|--------|----------|-------------|
| `name` | string | ✅ | the name of the method |
| `arg_type` | object | ✅ | What type of channel this is - see **OPCUAChannelType** |
| `enum_str` | string | ❌ | the string representation of the enum if the argument is an enum |

### OPCUAChannelType

The supported channel types are:
 - Float64
 - Int64
 - Uint8
 - Bool
 - Enum

### Micro Motion EtherNet/IP Hardware Names

For `device_type = MicroMotionEthernetIp`, the following `hardware_name` values are supported:

**Analog Input Channels (continuous measurements):**
- `mass_flow` - Mass flow rate measurement
- `temperature` - Temperature measurement
- `density` - Density measurement
- `drive_gain` - Drive gain measurement
- `totalizer_1` - Totalizer 1 cumulative value
- `inventory_1` - Inventory 1 volume measurement

**Integer Input Channels (discrete values):**
- `status_severity` - Status severity level (integer)
- `status_counter` - Status counter value (integer)

**Digital Input Channels (alert status bits):**
- `alert_electronics_failure` - Electronics failure alert
- `alert_sensor_failed` - Sensor failure alert
- `alert_configuration_error` - Configuration error alert
- `alert_drive_overrange` - Drive over-range alert
- `alert_tube_not_full` - Tube not full alert

**Command Output Channels (momentary commands):**
- `cmd_reset_totals` - Reset all process totals
- `cmd_start_zero` - Start sensor zero calibration
- `cmd_reset_totalizer_1` - Reset totalizer 1
- `cmd_reset_totalizer_2` - Reset totalizer 2
- `cmd_start_all_totals` - Start all totalizers
- `cmd_stop_all_totals` - Stop all totalizers
- `cmd_start_smv` - Start SMV (Smart Meter Verification)

**Note:** Command channels are momentary - set to `true` in RevelCode to trigger the command, then the system automatically resets to `false`.

---

### Module Objects

Each object in the `modules` array must contain:

| Field         | Type   | Required | Description                                               |
| ------------- | ------ | -------- | --------------------------------------------------------- |
| `module_type` | string | ✅       | The type of this module (e.g. CPX-E-EP)                   |
| `channels`    | array  | ✅       | List of channels on this module - see **Channel Objects** |

---

### EIP Module Objects

For `device_type = MicroMotionEthernetIp`, the `module` object must contain:

| Field         | Type   | Required | Description                                               |
| ------------- | ------ | -------- | --------------------------------------------------------- |
| `module_type` | string | ✅       | The type of this EIP module (e.g. MM5700)                |
| `module_role` | string | ✅       | The role of this module, typically "io"                  |
| `channels`    | array  | ✅       | List of channels on this module - see **Channel Objects** |

---

### Channel Objects

Each object in the `channels` array must contain:

| Field                       | Type   | Required | Description                                                                                                                                                                                                                               |
| --------------------------- | ------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `revel_name`                | string | ✅       | User-defined name                                                                                                                                                                                                                         |
| `hardware_name`             | string | ✅       | Physical device name                                                                                                                                                                                                                      |
| `channel_type`             | string | ✅       | `"AnalogInput"`, `"DigitalOutput"`, `"DigitalInput"`, `"GenericIntInput"`, `"GenericIntOutput"`, `"GenericFloatInput"`, `"GenericFloatOutput"`, `"Thermocouple"`                |
| `channel_details`           | object | ❌       | Optional, but required for `"AnalogInput"`, `"Thermocouple"`, and `"Counter"`                                                                                                                                                             |
| `channel_units`             | string | ❌       | Optional, used to specify the units for telemetry                                                                                                                                                                                         |
---

### Channel Details Based on `channel_type`

#### AnalogInput

If `channel_type` is `"AnalogInput"`, the `channel_details` object **must** contain:

| Field             | Type   | Required | Description                                                                                                           |
| ----------------- | ------ | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `signal_type`     | string | ✅       | Must be `"Current"` or `"Voltage"`                                                                                    |
| `scaling`         | object | ❌       | Defines the scaling function (default: `"None"`)                                                                      |
| `min`             | object | ❌       | Minimum value (default: `0.004` if `"Current"`, `-10.0` if `"Voltage"`)                                               |
| `max`             | object | ❌       | Maximum value (default: `0.020` if `"Current"`, `10.0` if `"Voltage"`)                                                |
| `terminal_config` | object | ❌       | Input terminal configuration, must be `"Default"`, `"RSE"`, `"NRSE"`, `"Diff"`, `"PseudoDiff"` (default: `"Default"`) |

The `scaling` object is optional, but if present, it must contain:

| Field  | Type   | Required                           | Description                            |
| ------ | ------ | ---------------------------------- | -------------------------------------- |
| `type` | string | ✅                                 | `"Linear"`, `"Quadratic"`, `"Cubic"`, `"Quartic"`, or `"None"` |

and the following additional required fields depending on type:

if `type` is `"Linear"`:

| Field  | Type   | Required                           | Description                            |
| ------ | ------ | ---------------------------------- | -------------------------------------- |
| `m`    | number | ✅                                  | Slope value for linear scaling         |
| `b`    | number | ✅                                  | Intercept value for linear scaling     |

if `type` is `"Quadratic"`:
| Field  | Type   | Required                           | Description                            |
| ------ | ------ | ---------------------------------- | -------------------------------------- |
| `a`    | number | ✅                                  | a in ax^2 + bx + c                     |
| `b`    | number | ✅                                  | b in ax^2 + bx + c                     |
| `c`    | number | ✅                                  | c in ax^2 + bx + c                     |

if `type` is `"Cubic"`:
| Field  | Type   | Required                            | Description                            |
| ------ | ------ | ----------------------------------  | -------------------------------------- |
| `a`    | number | ✅                                  | a in ax^3 + bx^2 + cx + d              |
| `b`    | number | ✅                                  | b in ax^3 + bx^2 + cx + d              |
| `c`    | number | ✅                                  | c in ax^3 + bx^2 + cx + d              |
| `d`    | number | ✅                                  | d in ax^3 + bx^2 + cx + d              |

if `type` is `"Quartic"`:
| Field  | Type   | Required                            | Description                            |
| ------ | ------ | ----------------------------------  | -------------------------------------- |
| `a`    | number | ✅                                  | a in ax^4 + bx^3 + cx^2 + dx + e       |
| `b`    | number | ✅                                  | b in ax^4 + bx^3 + cx^2 + dx + e       |
| `c`    | number | ✅                                  | c in ax^4 + bx^3 + cx^2 + dx + e       |
| `d`    | number | ✅                                  | d in ax^4 + bx^3 + cx^2 + dx + e       |
| `e`    | number | ✅                                  | e in ax^4 + bx^3 + cx^2 + dx + e       |

---

#### Thermocouple

If `channel_type` is `"Thermocouple"`, the `channel_details` object **must** contain:

| Field               | Type   | Required | Description                    |
| ------------------- | ------ | -------- | ------------------------------ |
| `temperature_units` | string | ✅       | Must be `"K"`, `"F"`, or `"C"` |
| `thermocouple_type` | string | ✅       | Must be `"J"`, `"K"`, `"N"` , `"R"` , `"S"` , `"T"` , `"B"` , `"E"` |
| `cjc_temperature`   | number | ❌       | Cold junction temperature, if not provided, uses cold-junction compensation channel built into the terminal block. |
| `adc_timing_mode`   | string | ❌       | ADC timing mode, must be `"Automatic"`, `"HighResolution"`, `"HighSpeed"`, `"Best50HzRejection"`, or `"Best60HzRejection"` |

---

#### RTD

If `channel_type` is `"RTD"`, the `channel_details` object **must** contain:

| Field                | Type   | Required | Description                                                                                                                |
| -------------------- | ------ | -------- | -------------------------------------------------------------------------------------------------------------------------- |
| `temperature_units`  | string | ✅       | Must be `"K"`, `"F"`, or `"C"`                                                                                             |
| `rtd_type`           | string | ✅       | Temperature Coefficient of Resistance, must be `"Pt3750"`, `"Pt3851"`, `"Pt3911"`, `"Pt3916"`, `"Pt3920"`, or `"Pt3928"`   |
| `resistance_config`  | string | ✅       | Must be `"TwoWire"`, `"ThreeWire"`, or `"FourWire"`                                                                        |
| `excitation_current` | number | ✅       | The amount of excitation in amps that the sensor requires.                                                                 |
| `min`                | number | ✅       | Minimum value expected to be measured                                                                                      |
| `max`                | number | ✅       | Maximum value expected to be measured                                                                                      |
| `r0`                 | number | ✅       | The sensor resistance in ohms at 0°C                                                                                       |
| `adc_timing_mode`    | string | ❌       | ADC timing mode, must be `"Automatic"`, `"HighResolution"`, `"HighSpeed"`, `"Best50HzRejection"`, or `"Best60HzRejection"` |

---

#### Counter

If `channel_type` is `"Counter"`, the `channel_details` object **must** contain:

| Field  | Type   | Required | Description              |
| ------ | ------ | -------- | ------------------------ |
| `mode` | object | ✅       | Defines the counter mode |

The `mode` object must contain:

| Field            | Type   | Required                                 | Description                                                                                       |
| ---------------- | ------ | ---------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `type`           | string | ✅                                       | `"PulseGeneration"`, `"DynAvgFrequencyInput"`, or  `"PulseInput"`                                 |
| `frequency`      | number | ✅ (only available if  if `type` is `"PulseGeneration"`) | frequencey of the pulse generation                                                                |
| `duty_cycle`     | number | ✅ (only available if  if `type` is `"PulseGeneration"`) | Duty cycle of the pulse generation                                                                |
| `pulse_terminal` | string | ❌ (only available if `type` is `"PulseGeneration"`) | Specifies on which terminal to generate pulses (default behavior if not provided, typically PFI0) |
| `commandable`    | bool   | ❌ (only available if `type` is `"PulseGeneration"`) | Whether this counter channel is commandable (exposes flags to enable/disable counter)             |
| `min_freq`       | number | ✅ (only available if `type` is `"DynAvgFrequencyInput"`) | Specifies the minimum frequency you expect to measure |
| `max_freq`       | number | ✅ (only available if `type` is `"DynAvgFrequencyInput"`) | Specifies the maximum frequency you expect to measure |
| `measurement_time` | number | ✅ (only available if `type` is `"DynAvgFrequencyInput"`) | The period of time over which to take the frequency measurement (0.0 to disable) |
| `divisor`          | number | ✅ (only available if `type` is `"DynAvgFrequencyInput"`) | The number of periods over which to take the frequency measurement (0 to disable) |

Note if rerouting the `pulse_terminal`, NI DAQs utilize something called "lazy uncommit" wherein the terminal used for output will continue to be connected even after a task is completed until it's needed for something else. This can be resolved either by configuring a DO task that utilizes the same line or by resetting DAQmx if changing terminals.

---

### High Speed Channels

#### HighSpeedAnalogInput
If `channel_type` is `"HighSpeedAnalogInput"`, the `channel_details` object **must** contain:

| Field                | Type   | Required | Description                                                         |
| -------------------- | ------ | -------- | ------------------------------------------------------------------- |
| `rate`               | number | ✅       | The desired sampling rate (Hz) to log the high speed data. The actual sampling rate may be snapped by the device to a nearby supported rate (e.g. desired 50 kHz -> actual 51.2 kHz). |
| `min`                | number | ✅       | Minimum expected value                                              |
| `max`                | number | ✅       | Maximum expected value                                              |
| `signal_type`        | string | ✅       | Must be `"Current"` or `"Voltage"`                                  |
| `scaling`            | number | ❌       | Defines the scaling function (default: `None`)                      |
| `iepe_config`            | object | ❌       | provides IEPE Configuration Options (default: `None`)                      |

#### IEPEConfig Object
| `excitation_val`     | number | ✅       | the excitation value to provide |
| `excitation_source`  | string | ✅       | 'internal' or 'external'        |

#### HighSpeedAccelerometer
If `channel_type` is `"HighSpeedAccelerometer"`, the `channel_details` object **must** contain:

| Field                | Type   | Required | Description                                                         |
| -------------------- | ------ | -------- | ------------------------------------------------------------------- |
| `rate`               | number | ✅       | The desired sampling rate (Hz) to log the high speed data. The actual sampling rate may be snapped by the device to a nearby supported rate (e.g. desired 50 kHz -> actual 51.2 kHz). |
| `min`                | number | ❌       | Minimum expected value in (g) (default: `-5.0`)                     |
| `max`                | number | ❌       | Maximum expected value in (g) (default: `5.0`)                      |
| `sensitivity`        | number | ❌       | Sensitivity of the accelerometer in volts/g (default: `.01043`)     |
| `excitation_current` | number | ❌       | The amount of excitation that the sensor requires (default: `.002`) |
| `scaling`            | number | ❌       | Defines the scaling function (default: `None`)                      |

Additionally, a channel in the following form **must** be defined in RevelCode for all High Speed Channels:

```python
# Provide a flag to use to toggle high speed data capture
channel |<DEVICE_NAME>_ai_high_speed_<RATE>_hz.enabled|: bool
```

For example, for a `device_name` of "cDAQ9189_20895CC" and a `rate` of "50000",
the channel to declare in RevelCode would be:

```python
channel |cDAQ9189_20895CC_ai_high_speed_50000_hz.enabled|: bool
```

This channel can be commanded to `True` through the Revel UI or through
automation to trigger persistence of highspeed data. Data will be logged until
the channel is set to `False` again. Keep in mind that high rate data will
accumulate quickly, and each Revel instance has a hard cap on the quantity of
data that can be stored before samples are dropped.

Logged high speed data will be available for download in compressed Parquet
format from the "Logs" page in the Revel UI shortly after the data capture is
toggled off. Downsampled, standard-rate telemetry is always available in
real-time through the UI.

Similar to the standard `AnalogInput` channels, High Speed channels also supports `scaling` which must contain:

| Field  | Type   | Required                           | Description                            |
| ------ | ------ | ---------------------------------- | -------------------------------------- |
| `type` | string | ✅                                 | `"Linear"`, `"Quadratic"`, or `"None"` |
| `m`    | number | ❌ (✅ if `type` is `"Linear"`)    | Slope value for linear scaling         |
| `b`    | number | ❌ (✅ if `type` is `"Linear"`)    | Intercept value for linear scaling     |
| `a`    | number | ❌ (✅ if `type` is `"Quadratic"`) | a in ax^2 + bx + c                     |
| `b`    | number | ❌ (✅ if `type` is `"Quadratic"`) | b in ax^2 + bx + c                     |
| `c`    | number | ❌ (✅ if `type` is `"Quadratic"`) | c in ax^2 + bx + c                     |

---

#### DigitalInput & DigitalOutput

For `"DigitalInput"` and `"DigitalOutput"`, the `channel_details` object is **optional** and does not require any specific fields.

---

## ✅ Example Valid Wiring List

```json
{
  "system_name": "TestSystem",
  "files": ["fileA.rvl", "fileB.rvl"],
  "devices": [
    {
      "device_type": "NISystem",
      "channels": [
        {
          "revel_name": "sensor_1",
          "hardware_name": "cDAQ3Mod1/ai4",
          "channel_type": "Thermocouple",
          "channel_details": {
            "temperature_units": "C"
          }
        },
        {
          "revel_name": "sensor_2",
          "hardware_name": "cDAQ2Mod3/ai4",
          "channel_type": "AnalogInput",
          "channel_details": {
            "signal_type": "Voltage",
            "scaling": {
              "type": "Linear",
              "m": 1.5,
              "b": 0.2
            }
          }
        },
        {
          "revel_name": "sensor_2",
          "hardware_name": "cDAQ2Mod3/ai4",
          "channel_type": "AnalogInput",
          "channel_details": {
            "signal_type": "Voltage",
            "scaling": {
              "type": "None"
            }
          }
        },
        {
          "revel_name": "valve_1",
          "hardware_name": "cDAQ5Mod7/port0/line2",
          "channel_type": "DigitalOutput"
        },
        {
          "revel_name": "digital_sensor1",
          "hardware_name": "cDAQ5Mod2/port0/line5",
          "channel_type": "DigitalInput"
        }
      ]
    },
    {
      "device_type": "LabJack",
      "device_name": "My_T7",
      "ip_address": "192.168.137.33",
      "stream_config": {
        "scan_rate": 50000.0,
        "num_addresses": 1
      },
      "channels": [
        {
          "revel_name": "test_ain0",
          "hardware_name": "AIN0",
          "channel_type": "AnalogInput",
          "channel_details": {
            "signal_type": "Voltage",
            "scaling": {
              "type": "None"
            }
          },
          "stream_in": true
        },
        {
          "revel_name": "analog_out",
          "hardware_name": "DAC0",
          "channel_type": "AnalogOutput",
          "channel_details": {
            "signal_type": "Voltage",
            "scaling": {
              "type": "None"
            }
          }
        },
        {
          "revel_name": "analog_out_fb",
          "hardware_name": "DAC0",
          "channel_type": "AnalogInput",
          "channel_details": {
            "signal_type": "Voltage",
            "scaling": {
              "type": "None"
            }
          }
        }
      ]
    },
    {
      "device_type": "MicroMotionEthernetIp",
      "device_name": "FlowMeter_01",
      "ip_address": "192.168.1.100",
      "module": {
        "module_type": "MM5700",
        "module_role": "io",
        "channels": [
          {
            "revel_name": "mass_flow_rate",
            "hardware_name": "mass_flow",
            "channel_type": "AnalogInput",
            "channel_details": {
              "signal_type": "Voltage",
              "scaling": {
                "type": "None"
              }
            }
          },
          {
            "revel_name": "fluid_temperature",
            "hardware_name": "temperature",
            "channel_type": "AnalogInput",
            "channel_details": {
              "signal_type": "Voltage",
              "scaling": {
                "type": "None"
              }
            }
          },
          {
            "revel_name": "fluid_density",
            "hardware_name": "density",
            "channel_type": "AnalogInput",
            "channel_details": {
              "signal_type": "Voltage",
              "scaling": {
                "type": "None"
              }
            }
          },
          {
            "revel_name": "total_volume",
            "hardware_name": "totalizer_1",
            "channel_type": "AnalogInput",
            "channel_details": {
              "signal_type": "Voltage",
              "scaling": {
                "type": "None"
              }
            }
          },
          {
            "revel_name": "device_status",
            "hardware_name": "status_severity",
            "channel_type": "GenericIntInput"
          },
          {
            "revel_name": "electronics_fault",
            "hardware_name": "alert_electronics_failure",
            "channel_type": "DigitalInput"
          },
          {
            "revel_name": "sensor_fault",
            "hardware_name": "alert_sensor_failed",
            "channel_type": "DigitalInput"
          },
          {
            "revel_name": "reset_totals_cmd",
            "hardware_name": "cmd_reset_totals",
            "channel_type": "DigitalOutput"
          },
          {
            "revel_name": "zero_sensor_cmd",
            "hardware_name": "cmd_start_zero",
            "channel_type": "DigitalOutput"
          }
        ]
      }
    }
  ]
}
```
