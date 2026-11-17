# `bioscout.emg.channels`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/channels.py)

Inspect a c3d's analog channels and write the emg_map for session.yaml.

    python -m bioscout.emg.channels TRIAL.c3d              # the table  
    python -m bioscout.emg.channels TRIAL.c3d --yaml       # emg_map stub  
    python -m bioscout.emg.channels TRIAL.c3d --yaml -o emg_map.yaml

WHY THIS EXISTS  
    `emg_map` is the only statement in a project of which analog channel is  
    which muscle, and until now it was written by hand from a channel list  
    nobody could see without opening the c3d in Vicon.

    That produced a silent, expensive failure, already documented in  
    `exportC3D._resolve_emg_channels`: subject 022's c3d carries 32 channels  
    containing the word "Voltage" -- 16 named ``Voltage_<n>-<MUSCLE>`` at  
    0.4-3.4 V, which ARE the conditioned EMG, and 16 bare ``Voltage_<n>`` at  
    0.01-0.04 V, which are unused inputs recording noise. A substring match on  
    "Voltage" took all 32, and every EMG-informed result solved before it was  
    caught had read the wrong columns.

    Nothing about that is visible in a filename. It IS visible in the  
    amplitudes, which is why this prints them: the two populations differ by  
    two orders of magnitude and the table separates instantly.

WHAT IT DOES NOT DO  
    It does not guess which muscle a channel belongs to beyond reading the  
    tag the operator typed into the c3d. An untagged channel is reported as  
    untagged, not matched by position or by neighbour -- guessing that is how  
    a muscle ends up driven by the channel next to it.

## Contents

- [`read_channels`](#read_channels) — [(label, n, vmin, vmax, rms)] for every analog channel.
- [`classify`](#classify) — Split into (tagged, untagged, other) and mark the quiet ones.
- [`report`](#report) — 
- [`to_yaml`](#to_yaml) — An emg_map stub keyed on the TAGGED channel names, muscles left blank.
- [`main`](#main) — 

### `read_channels`

```python
read_channels(c3d_path)
```

| input | type | default |
|---|---|---|
| `c3d_path` | – | required |

[(label, n, vmin, vmax, rms)] for every analog channel.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/channels.py#L42)</sub>

### `classify`

```python
classify(chans, emg_hint='voltage', quiet_ratio=10.0)
```

| input | type | default |
|---|---|---|
| `chans` | – | required |
| `emg_hint` | – | `'voltage'` |
| `quiet_ratio` | – | `10.0` |

Split into (tagged, untagged, other) and mark the quiet ones.

`quiet_ratio`: a channel whose RMS is this many times below the MEDIAN of  
the tagged channels is almost certainly an unused input. Relative, not an  
absolute threshold -- amplifier gain differs between labs, the two  
populations' SEPARATION does not.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/channels.py#L76)</sub>

### `report`

```python
report(c3d_path, emg_hint='voltage')
```

| input | type | default |
|---|---|---|
| `c3d_path` | – | required |
| `emg_hint` | – | `'voltage'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/channels.py#L108)</sub>

### `to_yaml`

```python
to_yaml(tagged, indent='  ')
```

| input | type | default |
|---|---|---|
| `tagged` | – | required |
| `indent` | – | `'  '` |

An emg_map stub keyed on the TAGGED channel names, muscles left blank.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/channels.py#L137)</sub>

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/channels.py#L152)</sub>
