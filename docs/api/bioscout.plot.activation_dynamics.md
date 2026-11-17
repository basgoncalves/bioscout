# `bioscout.plot.activation_dynamics`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/activation_dynamics.py)

bioscout.plot.activation_dynamics - effect of CEINMS c1, c2 and shape factor A  
on excitation -> activation (Lloyd & Besier 2003).

    u(t) = alpha*e(t-d) - beta1*u(t-1) - beta2*u(t-2)  
    beta1 = c1 + c2,  beta2 = c1*c2,  alpha = 1 + beta1 + beta2  
    a(t) = (exp(A*u) - 1) / (exp(A) - 1)          (A -> 0: linear)

    python -m bioscout.plot.activation_dynamics [out.png]

## Contents

- [`neural_activation`](#neural_activation) — 
- [`muscle_activation`](#muscle_activation) — 
- [`excitation`](#excitation) — 0.3 s pulse to 1, then a 0.4 s ramp 0 -> 0.5 -> 0.
- [`plot`](#plot) — 

### `neural_activation`

```python
neural_activation(e, c1, c2, d=0)
```

| input | type | default |
|---|---|---|
| `e` | – | required |
| `c1` | – | required |
| `c2` | – | required |
| `d` | – | `0` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/activation_dynamics.py#L18)</sub>

### `muscle_activation`

```python
muscle_activation(u, A)
```

| input | type | default |
|---|---|---|
| `u` | – | required |
| `A` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/activation_dynamics.py#L28)</sub>

### `excitation`

```python
excitation(t)
```

| input | type | default |
|---|---|---|
| `t` | – | required |

0.3 s pulse to 1, then a 0.4 s ramp 0 -> 0.5 -> 0.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/activation_dynamics.py#L32)</sub>

### `plot`

```python
plot(out=None, cs=(-0.9, -0.7, -0.5, -0.3, -0.1, 0.0), shapes=(0, -0.5, -1.1, -2, -3))
```

| input | type | default |
|---|---|---|
| `out` | – | `None` |
| `cs` | – | `(-0.9, -0.7, -0.5, -0.3, -0.1, 0.0)` |
| `shapes` | – | `(0, -0.5, -1.1, -2, -3)` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/activation_dynamics.py#L40)</sub>
