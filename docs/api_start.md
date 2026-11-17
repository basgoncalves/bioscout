## Where to start

| you want to... | look at |
|---|---|
| open a session and run stages | [`bioscout.session.recording.Session`](bioscout.session.recording.md#session), [`bioscout.session.iteration.Iteration`](bioscout.session.iteration.md#iteration) (`run`, `scale_model`, `run_emg_normalise`) |
| work on one trial of one iteration | [`bioscout.core.analysis.Analyse`](bioscout.core.analysis.md#analyse) (`run_ik`, `run_id`, `run_ma`, `run_so`, `run_jra`, `run_jra_contributions`, `plot_*`) |
| understand session.yaml keys | [`bioscout.session.config`](bioscout.session.config.md) (`SessionKeys`, `IterationKeys`) |
| SO reserve / residual actuators | [`bioscout.simulate.so_actuators`](bioscout.simulate.so_actuators.md) (`plan`, `percent_spec`, `percent_reserves`) |
| muscle contributions to JCF | [`bioscout.core.jcf_contributions`](bioscout.core.jcf_contributions.md) (`decompose`, `build_groups`, `summarise`) |
| folder layout resolvers | [`bioscout.session.layout`](bioscout.session.layout.md) |
| figures | [`bioscout.plot`](bioscout.plot.md) (`task_figure.TaskStrip`, `emg_figure`, `jcf_coverage`, ...) |
