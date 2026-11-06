"""ScaleTool driving: build a scaled model, and place its markers.

Joins ``measurements.py`` (MeasurementSet construction) and ``model_scaler.py``
(the GUI's wrapper) in ``bioscout.model.scale``. Despite its name,
``place_markers_via_ik`` edits the model's marker placements -- it does not run
a simulation, which is why it is here and not under ``simulate``.

Split out of the old ``bioscout/utils/openSim.py`` (docs/RESTRUCTURE_PLAN.md,
stage 6) -- the code is unchanged, only its address.
"""
import os
import opensim as osim

try:                                    # the project's settings.py, if it has one
    from bioscout import settings
except Exception:                       # noqa: BLE001 - absent or mid-cycle
    settings = None
from bioscout.model.opensim_base import (_osim_quiet_ctx, _quiet_model,
                                         _quiet_osim)
from bioscout.model.edit.osim_ops import _strip_trailing_nulls


def scale_model_from_xml(setup_xml_path, generic_model_path, static_trc_path, scaled_model_path, mass=None):
    """
    Scale an OpenSim model using a pre-existing ScaleTool setup XML (preserving its
    MeasurementSet, MarkerPlacer IK tasks, etc.) while overriding the key file paths
    and optionally the subject mass.

    Args:
        setup_xml_path (str): Path to the ScaleTool setup XML file.
        generic_model_path (str): Path to the unscaled generic .osim model.
        static_trc_path (str): Path to the static trial TRC file.
        scaled_model_path (str): Absolute path for the output scaled .osim model.
        mass (float, optional): Subject mass in kg. Defaults to model total mass.
    """
    scale_tool = osim.ScaleTool(setup_xml_path)

    base_folder = os.path.dirname(setup_xml_path)

    if mass is not None:
        scale_tool.setSubjectMass(mass)

    # GenericModelMaker
    scale_tool.getGenericModelMaker().setModelFileName(generic_model_path)

    # ModelScaler
    model_scaler = scale_tool.getModelScaler()
    model_scaler.setApply(True)
    model_scaler.setMarkerFileName(os.path.basename(static_trc_path))
    model_scaler.setOutputModelFileName(os.path.relpath(scaled_model_path, base_folder))
    model_scaler.setOutputScaleFileName('scale_set.xml')

    # MarkerPlacer
    marker_placer = scale_tool.getMarkerPlacer()
    marker_placer.setApply(True)
    marker_placer.setMarkerFileName(os.path.basename(static_trc_path))
    marker_placer.setOutputModelFileName(os.path.relpath(scaled_model_path, base_folder))
    marker_placer.setOutputMarkerFileName('static_output.trc')

    # print scale tool setup xml
    os.chdir(base_folder)
    scale_tool.printToXML(os.path.join(base_folder, 'setup_scale.xml'))
    print(f"Modified ScaleTool setup saved to: {os.path.join(os.path.dirname(scaled_model_path), 'setup_scale.xml')}")

    output = scale_tool.run()
    
    if not output:
        print(f"Scaled model saved to: {scaled_model_path}")
    else:
        print("Error: Scaling failed. Check the ScaleTool setup and input files.")

    return scale_tool

def _sanitize_markerset_xml(src_path, skip_names, out_dir):
    """Write a copy of an OpenSim marker-set XML with markers removed that would
    crash ScaleTool's MarkerPlacer: those named in ``skip_names`` and any marker
    parented to ground (``<socket_parent_frame>`` referencing ground). Returns the
    sanitized file path, or None if nothing was removed."""
    import re
    txt = open(src_path, errors="replace").read()
    skipU = {str(s).upper() for s in (skip_names or set())}
    removed = []
    def _filt(m):
        name, body = m.group(1), m.group(2)
        pf = re.search(r'<socket_parent_frame>([^<]+)', body)
        frame = (pf.group(1) if pf else "").strip().lower()
        if name.upper() in skipU or frame.endswith("ground"):
            removed.append(name)
            return ""
        return m.group(0)
    new = re.sub(r'<Marker name="([^"]+)">(.*?)</Marker>\s*', _filt, txt, flags=re.S)
    if not removed:
        return None
    out = os.path.join(out_dir,
                       os.path.splitext(os.path.basename(src_path))[0] + "_scaleready.xml")
    with open(out, "w") as f:
        f.write(new)
    print(f"[scale] dropped unplaceable markers from marker set: {removed} -> {os.path.basename(out)}")
    return out

def scale_model(generic_opensim_model_path, static_trc_path, scaled_model_path, scale_setup_output_dir=None, mass=None, time_range=None, marker_set_file=None, linear_scaling=True, marker_placer=False, ik_weights=None, setup_xml_path=None, run=True, marker_aliases=None, measurement_spec=None, scale_tool=None):
    """
    Scale an OpenSim model using the ScaleTool based on static marker data from a TRC file.

    The ScaleTool has two independent stages, exposed here as booleans that map
    1:1 onto OpenSim's own ``ModelScaler`` and ``MarkerPlacer``:

      * ``linear_scaling`` (ModelScaler) — dimensional scaling from marker
        distances. Turn OFF for an already-personalised model (e.g. MRI/TPS
        geometry) so its segment sizes are NOT changed.
      * ``marker_placer`` (MarkerPlacer) — move the model's markers onto the
        subject's static-trial markers (with an IK pass). Useful even when
        ``linear_scaling`` is off, so markers line up for IK. Off by default
        because it is memory-heavy with 100+ marker sets.

    Combinations: both True = classic scale+placement; linear only = size but
    keep template markers; placer only = keep geometry, re-place markers
    (MRI case); both False = copy the model through unchanged.

    Args:
        scale_setup_output_dir: Directory where to save scale_setup.xml (defaults to scaled_model directory)
        ik_weights: ``{marker: weight}`` for the standalone marker-registration
            IK. A weight of 0 drops the marker from the pass entirely. Only
            used when ``marker_placer`` is on; ignored otherwise. Default None
            = every marker weighted 1.0, which is what this always did.
        marker_aliases: ``{expected_name: name_this_lab_records}``. The default
            measurement spec and the joint-centre construction name the
            Vicon-CGM/powerlifting markers; a lab spelling them differently
            (FAIS records LSACR/RSACR for LPSI/RPSI, RLFC/RMFC for RKNEL/RKNEM)
            gets NO joint centre and almost no measurements without this, which
            scales the pelvis and leaves the femurs generic — silently.
            ``bioscout scale`` works this map out by asking.
        measurement_spec: ``[(name, [(a, b), ...], {body: axes}), ...]`` to use
            instead of ``measurements.DEFAULT_SPEC`` (which is written for the
            powerlifting/Vicon-CGM protocol). ``marker_aliases`` still apply to
            it. session.yaml: ``scale_measurements`` (see
            ``measurements.spec_from_config``).
        scale_tool: a ScaleTool setup .xml used as the TEMPLATE: its
            MeasurementSet, scaling order and preserve_mass_distribution are
            used as written; its paths, mass and time range are ignored and
            filled from the arguments here. ``measurement_spec`` is then
            unused. session.yaml: ``iterations.<name>.scale_tool``.
        setup_xml_path: Where to write the ScaleTool setup. Defaults to
            ``<scale_setup_output_dir>/scale_setup.xml``. This file is the
            record of what was actually applied — the MeasurementSet, the
            joint-centre-augmented TRC, the time range — and is the first thing
            to read when a scaled model looks wrong.
        run: False writes the setup and returns its path WITHOUT scaling. The
            setup references files under ``_temp_scaling/`` (the augmented TRC,
            the sanitised model), so that folder is kept in this mode — the
            setup is loadable in the OpenSim GUI as written.

    Returns:
        The setup XML path when ``run=False``; otherwise None.
    """
    import shutil as _shutil
    from bioscout.model.scale import measurements as _sm
    # Apply the configured OpenSim log level right here (lowercase — OpenSim
    # ignores "Error") so ScaleTool's geometry [warning] spam is quiet.
    try:
        _lvl = getattr(getattr(settings, "BatchSettings", None), "opensim_log_level", None)
        if _lvl:
            osim.Logger.setLevelString(str(_lvl).lower())
    except Exception:
        pass
    # Self-heal a corrupt generic: some TPS/warping tools pad the .osim with
    # trailing NUL bytes after </OpenSimDocument>. OpenSim loads it but ScaleTool's
    # MarkerPlacer then segfaults / throws "string too long". Strip the padding
    # (in place, with a .nulbak backup) so scaling works.
    generic_opensim_model_path = _strip_trailing_nulls(generic_opensim_model_path)
    # Neither stage requested → nothing for the ScaleTool to do; pass the model
    # through unchanged so downstream steps still find scaled_model_path.
    if not linear_scaling and not marker_placer:
        os.makedirs(os.path.dirname(scaled_model_path) or ".", exist_ok=True)
        if os.path.abspath(generic_opensim_model_path) != os.path.abspath(scaled_model_path):
            _shutil.copyfile(generic_opensim_model_path, scaled_model_path)
        print(f"[scale] linear_scaling=False, marker_placer=False → copied model "
              f"unchanged to: {scaled_model_path}")
        # "Unchanged" used to include the mass, so a model routed through this
        # branch kept whatever total mass its source had while every downstream
        # result was normalised by the subject's. Geometry still stays untouched.
        if mass is not None:
            try:
                _sm.set_total_mass(scaled_model_path, mass)
            except Exception as e:
                print(f"[scale] [WARNING] mass-only rescale failed: {e}")
        return
    model = _quiet_model(generic_opensim_model_path)
    state = model.initSystem()
    subject_mass = mass if mass is not None else model.getTotalMass(state)

    # MarkerPlacer runs an internal IK that SEGFAULTS on markers with no valid
    # placement — markers in BatchSettings.markers_to_skip and any marker rigidly
    # attached to ground (belt markers BL/BR). Strip them from a sanitized copy of
    # BOTH the model and the marker-set file, and scale from those, leaving the
    # user's originals untouched.
    try:
        from bioscout.utils import settings as _settings
        _skip = {str(s).upper() for s in
                 getattr(getattr(_settings, "BatchSettings", None), "markers_to_skip", []) or []}
    except Exception:
        _skip = set()
    _outdir = scale_setup_output_dir or os.path.dirname(scaled_model_path) or "."
    os.makedirs(_outdir, exist_ok=True)
    # Throwaway scaling intermediates (sanitized model/markerset, ScaleTool's
    # scale_setup.xml, the static-IK marker-registration .mot) live in a private
    # _temp_scaling/ subfolder that is removed on success — so they never clutter the
    # iteration folder. (Kept only if scaling raises, for debugging.)
    _tmp = os.path.join(_outdir, "_temp_scaling")
    os.makedirs(_tmp, exist_ok=True)
    generic_for_scaling = generic_opensim_model_path
    marker_set_for_scaling = marker_set_file
    _msd = model.updMarkerSet()
    _drop = []
    for _i in range(_msd.getSize()):
        _mk = _msd.get(_i)
        try:
            _fr = _mk.getParentFrame().getName().lower()
        except Exception:
            _fr = ""
        if _mk.getName().upper() in _skip or _fr == "ground":
            _drop.append((_i, _mk.getName()))
    if _drop:
        for _i, _ in sorted(_drop, reverse=True):
            _msd.remove(_i)
        model.finalizeConnections()
        generic_for_scaling = os.path.join(
            _tmp, os.path.splitext(os.path.basename(generic_opensim_model_path))[0] + "_scaleready.osim")
        model.printToXML(generic_for_scaling)
        print(f"[scale] dropped unplaceable markers from model: {[n for _, n in _drop]}")
    if marker_set_file and os.path.exists(marker_set_file):
        _san = _sanitize_markerset_xml(marker_set_file, _skip, _tmp)
        if _san:
            marker_set_for_scaling = _san

    # --- joint centres -----------------------------------------------------
    # ScaleTool measures DISTANCES BETWEEN MARKER PAIRS. The femur and tibia can
    # only be measured hip-to-knee-to-ankle, and a motion capture system cannot
    # see a joint centre — so the *WK virtual markers that markers_powerlifter.xml
    # puts on the body origins exist in every model but in NO TRC. Compute them
    # (Harrington hips, midpoint knees/ankles) into a scaling-only copy of the
    # static TRC. The ORIGINAL TRC is left untouched and is what marker
    # registration and every dynamic trial keep using.
    trc_for_scaling = static_trc_path
    if linear_scaling:
        try:
            trc_for_scaling = _sm.augment_static_trc(
                static_trc_path,
                os.path.join(_tmp, os.path.basename(static_trc_path).replace(".trc", "_jc.trc")),
                aliases=marker_aliases)
        except Exception as e:
            print(f"[scale] [WARNING] could not add joint centres to the static TRC: {e}")
            trc_for_scaling = static_trc_path

    # Resolve time range from TRC if not provided
    storage = osim.Storage(trc_for_scaling)
    t0, t1 = (time_range[0], time_range[1]) if time_range else (storage.getFirstTime(), storage.getLastTime())
    osim_time_range = osim.ArrayDouble()
    osim_time_range.append(t0)
    osim_time_range.append(t1)

    scaleTool = osim.ScaleTool(str(scale_tool)) if scale_tool else osim.ScaleTool()
    # A ScaleTool loaded from a template resolves every RELATIVE path against the
    # template's folder (setupFiles/), not the cwd: the output then lands beside the
    # template and the marker-placement pass cannot find it. Pin the subject path
    # and hand the tool absolute paths only. (2026-10-14)
    scaleTool.setPathToSubject("")
    generic_for_scaling = os.path.abspath(generic_for_scaling)
    trc_for_scaling = os.path.abspath(trc_for_scaling)
    scaled_model_path = os.path.abspath(scaled_model_path)
    if marker_set_for_scaling:
        marker_set_for_scaling = os.path.abspath(marker_set_for_scaling)
    scaleTool.setName("ModelScaling")
    scaleTool.setSubjectMass(subject_mass)

    # GenericModelMaker — sets the unscaled model (and optionally a marker set)
    gmm = scaleTool.getGenericModelMaker()
    gmm.setModelFileName(generic_for_scaling)
    if marker_set_for_scaling:
        gmm.setMarkerSetFileName(marker_set_for_scaling)

    # Determine where to save scale setup XML
    if scale_setup_output_dir is None:
        scale_setup_output_dir = os.path.dirname(scaled_model_path)
    os.makedirs(scale_setup_output_dir, exist_ok=True)

    # ModelScaler (dimensional scaling) — toggled by ``linear_scaling``.
    #
    # A default-constructed osim.ScaleTool() has an EMPTY MeasurementSet. OpenSim
    # accepts that without complaint: setApply(True) then scales every body by
    # 1.0 and only setSubjectMass() has any effect, so the output is generic
    # geometry wearing the subject's mass — a "scaled" model that is not scaled.
    # That silent failure is why this MeasurementSet is built and attached here,
    # and why verify_scaled() checks the result afterwards.
    modelScaler = scaleTool.getModelScaler()
    modelScaler.setApply(bool(linear_scaling))
    if linear_scaling and scale_tool:
        # The template's MeasurementSet, as written -- after checking every
        # marker it names is in the static TRC (joint centres included), since
        # ScaleTool otherwise dies deep inside with a bare marker name.
        _mset = modelScaler.getMeasurementSet()
        _have = set()
        try:
            _md = osim.MarkerData(trc_for_scaling)
            _have = {_md.getMarkerNames().get(i) for i in range(_md.getMarkerNames().getSize())}
        except Exception as e:
            print(f"[scale] [WARNING] could not list the TRC markers: {e}")
        _al = dict(marker_aliases or {})
        _missing = []
        for _i in range(_mset.getSize()):
            _m = _mset.get(_i)
            _ps = _m.getMarkerPairSet()
            for _j in range(_ps.getSize()):
                _pr = _ps.get(_j)
                for _k in (0, 1):
                    _n = _pr.getMarkerName(_k)
                    if _n in _al:
                        _pr.setMarkerName(_k, _al[_n]); _n = _al[_n]
                    if _have and _n not in _have:
                        _missing.append(f"{_m.getName()}:{_n}")
        if _mset.getSize() == 0:
            raise RuntimeError(f"scale_tool {scale_tool} has an EMPTY MeasurementSet")
        if _missing:
            raise RuntimeError(f"scale_tool {scale_tool}: markers not in the static TRC "
                               f"{trc_for_scaling}: {', '.join(_missing)}")
        print(f"[scale] ScaleTool template {os.path.basename(str(scale_tool))}: "
              f"{_mset.getSize()} measurements")
    elif linear_scaling:
        try:
            _mset, _rep, _skip_m = _sm.build_measurement_set(
                model, trc_for_scaling,
                spec=_sm.resolve_spec(measurement_spec or _sm.DEFAULT_SPEC, marker_aliases),
                model_markers=_sm.markerset_file_names(marker_set_for_scaling))
            if _mset.getSize() == 0:
                print("[scale] [ERROR] MeasurementSet is EMPTY — ScaleTool would apply a "
                      "scale factor of 1.0 to every body and return the generic model with "
                      "the subject's mass. Check the marker names above.")
                # Refuse instead of warning: the warning was printed for months
                # while every 'scaled' model stayed generic size.
                raise RuntimeError("empty MeasurementSet with linear_scaling=True "
                                   "(see the SKIPPED lines above)")
            try:
                modelScaler.setMeasurementSet(_mset)
            except Exception:
                pass
            # getModelScaler()/getMeasurementSet() hand back C++ references through
            # SWIG, but that is an assumption worth checking rather than trusting:
            # if the set did not land, append into the tool's own set instead, and
            # if THAT does not stick, say so instead of scaling by 1.0 in silence.
            if modelScaler.getMeasurementSet().getSize() != _mset.getSize():
                _tgt = modelScaler.getMeasurementSet()
                for _i in range(_mset.getSize()):
                    _tgt.cloneAndAppend(_mset.get(_i))
            _n = modelScaler.getMeasurementSet().getSize()
            if _n != _mset.getSize():
                print(f"[scale] [ERROR] the ScaleTool kept {_n} of {_mset.getSize()} "
                      f"measurements — scaling would be wrong or absent. Aborting is safer "
                      f"than shipping a generic model named 'scaled'.")
                raise RuntimeError("MeasurementSet did not attach to the ScaleTool")
            try:
                modelScaler.setScalingOrder(osim.ArrayStr("measurements", 1))
            except Exception:
                pass
            print(f"[scale] ScaleTool holds {_n} measurements")
        except Exception as e:
            print(f"[scale] [ERROR] could not build the MeasurementSet: {e}")
            raise
    modelScaler.setMarkerFileName(trc_for_scaling)
    modelScaler.setTimeRange(osim_time_range)
    modelScaler.setOutputModelFileName(scaled_model_path)
    # Keep the computed scale factors OUT of the throwaway _temp_scaling folder:
    # this file is the record of exactly what was applied to each body, and it is
    # the first thing to read when a result looks wrong.
    modelScaler.setOutputScaleFileName(os.path.join(_outdir, 'scale_factors.xml'))

    # MarkerPlacer (place model markers onto static-trial markers) — toggled by
    # ``marker_placer``. Off by default (memory-heavy with 100+ markers). When
    # linear_scaling is off but this is on, it operates on the (unscaled) model —
    # the MRI case — and writes the final model to scaled_model_path.
    # MarkerPlacer: NEVER use ScaleTool's own C++ MarkerPlacer stage — its internal
    # IK throws a HARD SIGSEGV (uncatchable in Python, so a try/except cannot recover)
    # on some complex models (Catelli high-hip-flexion, MRI Lerner-knee). Instead
    # ScaleTool does DIMENSIONAL SCALING ONLY, then markers are registered by a
    # standalone IK pass (place_markers_via_ik) — the same MarkerPlacer algorithm,
    # done by hand, which is numerically equivalent, validates markers first, and is
    # crash-safe.
    markerPlacer = scaleTool.getMarkerPlacer()
    markerPlacer.setApply(False)

    # Write the setup BEFORE running. Written after, a crash leaves nothing to
    # read — which is exactly when you want it. This is a real ScaleTool setup:
    # OpenSim serialises it, so the OpenSim GUI opens it.
    _setup_out = setup_xml_path or os.path.join(_outdir, "scale_setup.xml")
    try:
        os.makedirs(os.path.dirname(_setup_out) or ".", exist_ok=True)
        scaleTool.printToXML(_setup_out)
        # The tool object keeps ABSOLUTE paths (that is what the run below
        # resolves against, whatever the cwd), but the FILE gets relative ones:
        # OpenSim resolves a setup's paths against the setup's own folder, so a
        # relative setup still opens after the session folder moves or lands on
        # someone else's machine. Rewriting the file cannot affect the run.
        from bioscout.utils.paths import relativise_xml as _relx
        _nrel = _relx(_setup_out)
        print(f"[scale] ScaleTool setup written: {_setup_out}"
              + (f" ({_nrel} path(s) relative to it)" if _nrel else ""))
    except Exception as e:
        print(f"[scale] [WARNING] could not write the ScaleTool setup: {e}")
        _setup_out = None

    if not run:
        # Deliberately NOT removing _temp_scaling: the setup points into it.
        print(f"[scale] run=False — setup written, nothing scaled. Its inputs "
              f"live in {_tmp}")
        return _setup_out

    print(f"[scale] linear_scaling={bool(linear_scaling)}, marker_placer={bool(marker_placer)} "
          f"(marker placement via standalone IK, not ScaleTool MarkerPlacer)")
    if linear_scaling:
        scaleTool.run()                           # dimensional scaling only -> scaled_model_path
    else:
        # MRI/TPS case: geometry is already personalised and must not be touched.
        # But with ModelScaler off, NOTHING ever applies the subject's mass, so the
        # model silently keeps the generic's — which is why the MRI variants were
        # carrying 75.34 kg while every result was normalised by the real body mass.
        # Copy the geometry through, then rescale mass and inertia alone.
        if os.path.abspath(generic_for_scaling) != os.path.abspath(scaled_model_path):
            _shutil.copyfile(generic_for_scaling, scaled_model_path)
        if mass is not None:
            try:
                _sm.set_total_mass(scaled_model_path, mass)
            except Exception as e:
                print(f"[scale] [WARNING] mass-only rescale failed: {e}")
    if marker_placer:
        # Register markers against the ORIGINAL TRC with the joint centres stripped
        # from the marker set: they are regression estimates, not measurements, and
        # must never pull the model's real markers around during the IK pass.
        _ms_place = _sm.marker_placement_markerset(marker_set_for_scaling, _tmp)
        _sf = os.path.join(_outdir, 'scale_factors.xml') if linear_scaling else None
        place_markers_via_ik(scaled_model_path, static_trc_path, scaled_model_path,
                             marker_set_file=_ms_place, time_range=(t0, t1),
                             work_dir=_tmp, ik_weights=ik_weights, scale_set_file=_sf)
    # Prove the model actually changed size. Without this the empty-MeasurementSet
    # failure is invisible: the file exists, is named scaled.osim, and every
    # downstream stage runs happily on generic geometry.
    if linear_scaling:
        try:
            _sm.verify_scaled(generic_for_scaling, scaled_model_path)
        except Exception as e:
            print(f"[scale] [WARNING] post-scaling verification failed: {e}")
    # scaling succeeded — drop the throwaway intermediates. The setup XML above
    # names two of them (the joint-centre-augmented TRC and, if markers were
    # dropped, the sanitised model), so those paths no longer resolve: the setup
    # is a RECORD of what ran, not a re-runnable file. Call with run=False to
    # get one that is.
    # Keep the two files the setup NAMES, so scale_setup.xml is a re-runnable
    # record rather than one that points into a folder we are about to delete.
    # They move up beside the setup and the setup is repointed at them; the rest
    # of _temp_scaling (ScaleTool's own dump, the static-IK .mot) still goes.
    if _setup_out:
        try:
            _keep = [p for p in (trc_for_scaling, generic_for_scaling,
                                 marker_set_for_scaling)
                     if p and os.path.dirname(os.path.abspath(p)) == os.path.abspath(_tmp)]
            for _src in _keep:
                _dst = os.path.join(_outdir, os.path.basename(_src))
                if os.path.abspath(_src) != os.path.abspath(_dst):
                    _shutil.copyfile(_src, _dst)
            if _keep:
                _txt = open(_setup_out, "rb").read().decode("utf-8", "surrogateescape")
                for _src in _keep:
                    _b = os.path.basename(_src)
                    for _pat in (os.path.join("_temp_scaling", _b),
                                 "_temp_scaling/" + _b, "_temp_scaling\\" + _b):
                        _txt = _txt.replace(_pat, _b)
                open(_setup_out, "wb").write(_txt.encode("utf-8", "surrogateescape"))
                print(f"[scale] setup inputs kept beside it: "
                      f"{', '.join(os.path.basename(p) for p in _keep)}")
        except Exception as e:                  # noqa: BLE001 - convenience only
            print(f"[scale] [WARNING] could not preserve the setup's inputs: {e}")
    _shutil.rmtree(_tmp, ignore_errors=True)
    # Make the written model stand on its own: named after itself rather than
    # after ScaleTool, and with its meshes reachable from where it now lives.
    name_model_after_file(scaled_model_path)
    copy_geometry_beside(scaled_model_path, generic_opensim_model_path)
    print(f"Scaled model saved to: {scaled_model_path}")



def run_scale_setup(setup_xml_path, mass=None):
    """Run a ScaleTool setup XML exactly as written -- `bioscout model scale --setup`.

    No paths are overridden and nothing is re-enabled: what the file says is
    what runs. That is the point -- it makes a scaling run reproducible from
    the record `scale_model` leaves behind, and it opens a setup built in the
    OpenSim GUI.

    Two things worth knowing about a setup that `scale_model` wrote:

    * its MarkerPlacer is OFF. `scale_model` registers markers with a standalone
      IK pass instead, because ScaleTool's own MarkerPlacer throws bad_alloc on
      some complex models. Re-running the setup therefore reproduces the
      DIMENSIONAL scaling, not the marker placement -- run `place_markers_via_ik`
      after it if you need that too.
    * its paths are relative to the setup file, so the working directory has to
      be that folder. This chdirs there and restores the old one afterwards.

    Returns the ScaleTool exit status as a process return code (0 = scaled).
    """
    setup_xml_path = os.path.abspath(setup_xml_path)
    if not os.path.isfile(setup_xml_path):
        print(f"[scale] no such setup: {setup_xml_path}")
        return 1
    base = os.path.dirname(setup_xml_path)
    _cwd = os.getcwd()
    try:
        tool = osim.ScaleTool(setup_xml_path)
        if mass is not None:
            tool.setSubjectMass(float(mass))
            print(f"[scale] subject mass overridden: {float(mass):.2f} kg")
        os.chdir(base)                          # relative paths resolve from here
        print(f"[scale] running {os.path.basename(setup_xml_path)} in {base}")
        failed = tool.run()
    except Exception as e:                      # noqa: BLE001
        print(f"[scale] [ERROR] {type(e).__name__}: {e}")
        return 1
    finally:
        os.chdir(_cwd)
    if failed:
        print("[scale] [ERROR] ScaleTool reported a failure -- read its messages above")
        return 1
    print("[scale] setup ran")
    return 0


def name_model_after_file(osim_path, name=None):
    """Rename ``<Model name="...">`` to ``name`` (default: the file's stem).

    OpenSim's ScaleTool names its output after the TOOL, so every scaled model
    in every project lands as ``<Model name="ModelScaling">`` and the GUI's
    Navigator shows the same word for all of them. Nothing reads this name --
    it is the Navigator label and a couple of log lines -- so a failure here
    must never sink a scaling run.

    Rewrites BYTES, not text: these models are CRLF, and text mode would turn
    every CRLF into LF and rewrite ~15000 line endings for a 30-character
    rename. ``surrogateescape`` round-trips anything the decoder dislikes.
    """
    import re as _re
    name = name or os.path.splitext(os.path.basename(osim_path))[0]
    try:
        with open(osim_path, "rb") as _fh:
            txt = _fh.read().decode("utf-8", "surrogateescape")
        txt, n = _re.subn(r'(<Model\s+name=")([^"]*)(")',
                          lambda m: m.group(1) + name + m.group(3), txt, count=1)
        if n:
            with open(osim_path, "wb") as _fh:
                _fh.write(txt.encode("utf-8", "surrogateescape"))
            print(f"[scale] model named '{name}'")
        return bool(n)
    except Exception as e:                        # noqa: BLE001 - cosmetic only
        print(f"[scale] [WARNING] could not name the model: {e}")
        return False


def copy_geometry_beside(osim_path, source_model_path):
    """Copy the meshes ``osim_path`` references into ``<its folder>/Geometry/``.

    OpenSim resolves a bare ``<mesh_file>`` against the model's own folder, a
    ``Geometry/`` beside it, and its INSTALLED Geometry folder. A model scaled
    into a session folder therefore still finds the meshes OpenSim ships
    (r_tibia, pelvis, ribs...) and silently loses the ones that are specific to
    the generic it came from -- for GPK that is r_femur/l_femur/fem_cond/
    tib_plat, i.e. exactly the segments the joint moments are about. The model
    loads with every muscle, marker and joint intact and no femurs, and nothing
    downstream can tell.

    Copying them beside the output makes the scaled model portable, which is
    what ``bioscout model check --strict`` asks for. ~6 MB for GPK.
    """
    import re as _re
    try:
        src_dir = os.path.dirname(os.path.abspath(source_model_path))
        out_dir = os.path.dirname(os.path.abspath(osim_path))
        with open(osim_path, "rb") as _fh:
            txt = _fh.read().decode("utf-8", "surrogateescape")
        meshes = sorted(set(_re.findall(r"<mesh_file>\s*([^<]+?)\s*</mesh_file>", txt)))
        if not meshes:
            return 0
        roots = [os.path.join(src_dir, "Geometry"), src_dir]
        dest = os.path.join(out_dir, "Geometry")
        copied = missing = 0
        for f in meshes:
            base = os.path.basename(f)
            if os.path.isfile(os.path.join(out_dir, base)) or \
               os.path.isfile(os.path.join(dest, base)):
                continue                          # already resolvable from here
            src = next((os.path.join(r, f) for r in roots
                        if os.path.isfile(os.path.join(r, f))), None)
            if src is None:
                missing += 1
                continue
            os.makedirs(dest, exist_ok=True)
            _shutil.copyfile(src, os.path.join(dest, base))
            copied += 1
        if copied:
            print(f"[scale] copied {copied} mesh file(s) to {dest}")
        if missing:
            print(f"[scale] [WARNING] {missing} mesh(es) not found beside the generic "
                  f"-- `bioscout model check {osim_path}` will say which")
        return copied
    except Exception as e:                        # noqa: BLE001 - cosmetic only
        print(f"[scale] [WARNING] could not copy geometry: {e}")
        return 0


def _scale_markers_with_bodies(model, scale_set_file):
    """Multiply each marker's location by the scale factors of the body it sits on
    (its parent frame's base frame), read from a ScaleTool scale-set file."""
    import xml.etree.ElementTree as _ET
    sf = {}
    for sc in _ET.parse(scale_set_file).getroot().iter("Scale"):
        seg = (sc.findtext("segment") or "").strip()
        if seg and (sc.findtext("apply") or "true").strip() != "false":
            sf[seg] = [float(v) for v in (sc.findtext("scales") or "1 1 1").split()]
    model.finalizeConnections()
    ms = model.updMarkerSet()
    n = 0
    for i in range(ms.getSize()):
        mk = ms.get(i)
        try:
            body = mk.getParentFrame().findBaseFrame().getName()
        except Exception:
            continue
        f = sf.get(body)
        if not f:
            continue
        loc = mk.get_location()
        mk.set_location(osim.Vec3(loc.get(0) * f[0], loc.get(1) * f[1], loc.get(2) * f[2]))
        n += 1
    print(f"[scale] {n}/{ms.getSize()} marker-set locations scaled with their bodies "
          f"({os.path.basename(scale_set_file)}) before registration")


def place_markers_via_ik(model_path, static_trc, out_model_path,
                         marker_set_file=None, time_range=None, work_dir=None,
                         ik_weights=None, max_ik_seconds=2.0, scale_set_file=None):
    """Register a model's markers to the subject's STATIC pose WITHOUT ScaleTool's
    MarkerPlacer (which segfaults / throws bad_alloc on some complex models, e.g.
    the MRI/Lerner-knee model). Standard MarkerPlacer algorithm, done by hand:

      1. run a normal IK on the static trial (this path works where MarkerPlacer
         fails),
      2. move the model to the MEAN static pose,
      3. relocate each model marker to the averaged experimental marker position,
         expressed in that marker's parent frame.

    Writes the registered model to ``out_model_path``. Best-effort; on failure the
    base model is left as-is (markers un-registered)."""
    import numpy as _np
    _quiet_osim()
    model = _quiet_model(model_path)
    if marker_set_file and os.path.exists(marker_set_file):
        # NEVER swallow this. A rejected marker set leaves the model with the
        # GENERIC's own markers, IK then tracks only the names that happen to
        # exist in both the model and the TRC, and the failure surfaces three
        # stages later as impossible kinematics. It cost a night to find once.
        _before = model.getMarkerSet().getSize()
        try:
            # OpenSim 4.x exposes MarkerSet(), MarkerSet(str) and
            # MarkerSet(str, bool) -- there is NO MarkerSet(model, str), though
            # older bindings had one. Calling it raised TypeError on every
            # model and every subject; the swallowed exception left each model
            # with the GENERIC's markers and IK tracking whatever names
            # happened to coincide. Try the documented form first and keep the
            # legacy one only as a fallback.
            try:
                _ms = osim.MarkerSet(marker_set_file)
            except TypeError:
                _ms = osim.MarkerSet(model, marker_set_file)
            # updateMarkerSet APPENDS -- it does not replace. Left alone the
            # model ends up carrying both naming conventions (43 + 48 = 91),
            # which doubles the registration IK and registers markers that are
            # not the ones the data uses. Empty the model's own set first.
            _own = model.updMarkerSet()
            for _i in range(_own.getSize() - 1, -1, -1):
                _own.remove(_i)
            model.updateMarkerSet(_ms)
            model.finalizeConnections()
            # The marker set file holds GENERIC (unscaled) locations. ScaleTool's
            # MarkerPlacer registers markers that were scaled with their bodies;
            # without this the static-pose IK below runs on unscaled markers and
            # biases the registered pose (seen as a constant ~4 deg pelvis-tilt /
            # hip-flexion offset in every later IK). Scale them the same way.
            if scale_set_file and os.path.exists(scale_set_file):
                _scale_markers_with_bodies(model, scale_set_file)
            if model.getMarkerSet().getSize() != _ms.getSize():
                print(f"[scale] [WARNING] marker set applied but the model now "
                      f"has {model.getMarkerSet().getSize()} markers for a "
                      f"{_ms.getSize()}-marker file -- markers were merged, "
                      f"not replaced.")
            print(f"[scale] marker set applied: "
                  f"{os.path.basename(marker_set_file)} -- "
                  f"{model.getMarkerSet().getSize()} markers (was {_before})")
        except Exception as e:
            print(f"[scale] [ERROR] marker set {os.path.basename(marker_set_file)} "
                  f"was REJECTED: {type(e).__name__}: {e}")
            print(f"[scale] [ERROR] the model keeps its own {_before} marker(s). "
                  f"IK will track only the names present in BOTH the model and "
                  f"the TRC -- check the marker set's parent frames against this "
                  f"model's body names.")
    state = model.initSystem()

    md = osim.MarkerData(static_trc)
    try:
        md.convertToUnits(osim.Units(osim.Units.Meters))     # -> metres to match the model
    except Exception:
        pass
    t0 = md.getStartFrameTime() if time_range is None else float(time_range[0])
    t1 = md.getLastFrameTime() if time_range is None else float(time_range[1])

    # Step 2 below AVERAGES the IK result into a single static pose, so solving
    # every frame of a 20 s standing trial buys nothing: the subject is not
    # moving, and the mean over a couple of seconds is the same pose to well
    # inside marker noise. IK is by far the most expensive part of scaling, so
    # the window is capped by default. Pass max_ik_seconds=None for the whole
    # trial (the pre-3.0.4 behaviour).
    if max_ik_seconds and (t1 - t0) > float(max_ik_seconds):
        _mid = 0.5 * (t0 + t1)
        _half = 0.5 * float(max_ik_seconds)
        _t0, _t1 = _mid - _half, _mid + _half
        print(f"[scale] marker-registration IK over {_t1 - _t0:.2f} s of the "
              f"{t1 - t0:.2f} s static trial (centred; the pose is averaged "
              f"anyway). max_ik_seconds=None for all of it.")
        t0, t1 = _t0, _t1

    # 1) IK on the static trial
    _mot = (os.path.join(work_dir, os.path.splitext(os.path.basename(out_model_path))[0] + "_static_ik.mot")
            if work_dir else os.path.splitext(out_model_path)[0] + "_static_ik.mot")
    ik = osim.InverseKinematicsTool()
    # Marker weights for the registration pass. Without a task set every marker
    # is weighted 1.0, so a marker you know is badly placed pulls the static
    # pose exactly as hard as a reliable one — and the model's markers are then
    # registered to that pose.
    if ik_weights:
        try:
            _model_names = {model.getMarkerSet().get(_i).getName()
                            for _i in range(model.getMarkerSet().getSize())}
            _ts = osim.IKTaskSet()
            _used = _zero = 0
            for _n, _w in sorted(ik_weights.items()):
                if _n not in _model_names:
                    continue                      # in the TRC, not on the model
                _t = osim.IKMarkerTask()
                _t.setName(_n)
                _t.setWeight(float(_w))
                _t.setApply(float(_w) > 0)
                _ts.cloneAndAppend(_t)
                if float(_w) > 0:
                    _used += 1
                else:
                    _zero += 1
            if _ts.getSize():
                ik.set_IKTaskSet(_ts)
                print(f"[scale] marker registration IK: {_used} marker(s) weighted, "
                      f"{_zero} switched off")
        except Exception as e:
            print(f"[scale] [WARNING] could not apply marker weights to the "
                  f"registration IK ({e}); every marker weighted 1.0")
    ik.setModel(model)
    # Converge fully: the registration pose is averaged and every later IK inherits it. At
    # OpenSim's default accuracy (1e-5) the solver stops in the flat valley of this objective,
    # ~0.2-0.4 deg from the minimum (K2L static: hip flexion 0.35 deg), which moves the registered
    # markers by up to ~0.6 mm. A static trial is a few frames, so this costs nothing.
    ik.set_accuracy(1e-9)
    ik.setMarkerDataFileName(static_trc)
    ik.setStartTime(t0)
    ik.setEndTime(t1)
    ik.setOutputMotionFileName(_mot)
    # OpenSim defaults results_directory to './' (the PROCESS CWD) and
    # report_errors to True, so this registration pass used to drop
    # `_ik_marker_errors.sto` in whatever directory the run started from --
    # the project root -- overwritten by every model and session. Keep it
    # next to the model it belongs to.
    _ik_res = os.path.dirname(os.path.abspath(_mot))
    os.makedirs(_ik_res, exist_ok=True)
    try:
        ik.setResultsDir(_ik_res)
    except Exception:
        pass
    with _osim_quiet_ctx():
        ik.run()

    # 2) mean static pose
    sto = osim.Storage(_mot)
    try:
        if sto.isInDegrees():
            model.getSimbodyEngine().convertDegreesToRadians(sto)
    except Exception:
        pass
    cs = model.getCoordinateSet()
    for i in range(cs.getSize()):
        c = cs.get(i)
        arr = osim.ArrayDouble()
        try:
            sto.getDataColumn(c.getName(), arr)
            vals = [arr.getitem(k) for k in range(arr.getSize())]
        except Exception:
            vals = []
        if vals:
            try:
                c.setValue(state, float(_np.mean(vals)), False)
            except Exception:
                pass
    model.assemble(state)
    model.realizePosition(state)

    # 3) relocate markers to the averaged experimental positions
    ground = model.getGround()
    ms = model.updMarkerSet()
    nfr = md.getNumFrames()
    moved = 0
    for i in range(ms.getSize()):
        mk = ms.get(i)
        try:
            idx = md.getMarkerIndex(mk.getName())
        except Exception:
            idx = -1
        if idx < 0:
            continue
        acc = _np.zeros(3); n = 0
        for f in range(nfr):
            v = md.getFrame(f).getMarker(idx)
            x, y, z = v.get(0), v.get(1), v.get(2)
            if x == x:                                       # skip NaN
                acc += (x, y, z); n += 1
        if n == 0:
            continue
        p = acc / n
        try:
            pF = ground.findStationLocationInAnotherFrame(
                state, osim.Vec3(float(p[0]), float(p[1]), float(p[2])), mk.getParentFrame())
            mk.set_location(pF)
            moved += 1
        except Exception:
            pass
    model.finalizeConnections()
    model.printToXML(out_model_path)
    print(f"[scale] IK-based marker registration placed {moved}/{ms.getSize()} markers "
          f"-> {os.path.basename(out_model_path)}")
    # Registering a handful of a large marker set means the model and the data
    # disagree on NAMES: everything downstream still runs, and IK quietly solves
    # the pose from those few markers. Say so here, where it is still cheap.
    if ms.getSize() and moved < max(6, 0.5 * ms.getSize()):
        _mnames = {ms.get(i).getName() for i in range(ms.getSize())}
        print(f"[scale] [WARNING] only {moved} of {ms.getSize()} model markers "
              f"matched the static trial. IK cannot be trusted with this few -- "
              f"the model's markers are: {sorted(_mnames)}")
    return out_model_path
