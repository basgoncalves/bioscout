# `bioscout.emg`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/__init__.py)

EMG domain code: filtering, channel mapping, MVC normalisation, analysis.

A domain package, not a CLI verb -- ``session/`` (export, channel resolution)  
and ``simulate/ceinms/`` (excitation QC) both import from here, the same way  
everything already imports ``core/``.

    filter.py     filter-SETTINGS resolution (session.yaml -> BatchSettings  
                  -> defaults), not signal processing  
    normalise.py  rectify / envelope / session-max MVC normalisation  
    channels.py   channel-name -> muscle resolution  
    analysis.py   NMF synergies, CEINMS-readiness frequency QC  
    emg.py        the shared EMG data helpers

Nothing is imported eagerly (scipy/pandas stay unloaded until used).
