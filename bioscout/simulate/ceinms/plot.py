"""bioscout.simulate.ceinms.plot — Figures made from CEINMS output — calibration parameters, model
comparisons, moment tracking, optimisation results and muscle forces.

Split out of the former flat `utils/ceinms.py`; see the package
__init__ for why. The shared header (imports, the live `settings`
proxy) comes from `.shared`.
"""
from .shared import *          # noqa: F401,F403 — the common header


def plot_loop_results(CSVresultsPath=None):
    
    if not CSVresultsPath:
        CSVresultsPath = input("Enter path to CEINMS executable results CSV file: ").strip('"')
        
    df = pd.read_csv(CSVresultsPath)

    alphas = df['Alpha'].unique()
    betas = df['Beta'].unique()
    gammas = df['Gamma'].unique()
    combinations = [(a, b) for a in alphas for b in betas]
    
    # Set up the figure with 2x2 subplots
    fig, axes = plt.subplots(len(combinations), 2, figsize=(16, 12))
    fig.suptitle('Effects of Parameters on Model Performance', fontsize=16)
    axes = axes.flatten()
    
    for i, (alpha, beta) in enumerate(combinations): 
        cropped_df = df[(df['Alpha'] == alpha) & (df['Beta'] == beta)]
        
        # Plot RMSE
        ax_rmse = axes[i*2]
        ax_rmse.scatter(cropped_df['Gamma'], cropped_df['RMSE_Moments'], c='blue', label=f'Moments', s=60, alpha=0.7, edgecolors='black', linewidth=0.5)
        ax_rmse.scatter(cropped_df['Gamma'], cropped_df['RMSE_Excitations'], c='red', label='Excitations', s=60, alpha=0.7, edgecolors='black', linewidth=0.5)
        ax_rmse.set_ylabel('RMSE (%)')
        ax_rmse.set_xticklabels([])
        ax_rmse.grid(True, alpha=0.3)
        # ax_rmse.set_xscale('log')   
        
        # add text box with alpha and beta values
        textstr = f'Alpha: {alpha}\nBeta: {beta}'
        props = dict(boxstyle='round', facecolor='white', alpha=0.5)
        ax_rmse.text(0.05, 0.95, textstr, transform=ax_rmse.transAxes, fontsize=10, verticalalignment='top', bbox=props)
        ax_rmse.set_xticks(gammas)
        
        if i == 0:
            ax_rmse.legend()
        
        if i == len(combinations) - 1:
            ax_rmse.set_xlabel('Gamma')
            ax_rmse.set_xticklabels(gammas)
        else:
            ax_rmse.set_xticklabels([])
            
        
        # Plot R²
        ax_r2 = axes[i*2 + 1]
        ax_r2.scatter(cropped_df['Gamma'], cropped_df['R2_Moments'], c='blue', label='Moments', s=60, alpha=0.7, edgecolors='black', linewidth=0.5)
        ax_r2.scatter(cropped_df['Gamma'], cropped_df['R2_Excitations'], c='red', label='Excitations', s=60, alpha=0.7, edgecolors='black', linewidth=0.5)
        ax_r2.set_ylabel('R²')
        ax_r2.set_xticklabels([])
        ax_r2.grid(True, alpha=0.3)
        # ax_r2.set_xscale('log')
        ax_r2.set_ylim(0, 1)
        ax_r2.set_xticks(gammas)
        
        
        if i == len(combinations) - 1:
            ax_r2.set_xlabel('Gamma')
            ax_r2.set_xticklabels(gammas)
        else:
            ax_r2.set_xticklabels([])
    
    plt.tight_layout()
    
    # Print summary statistics
    print("Parameter Effects Summary:")
    print("="*50)
    print(f"Best RMSE_Moments: {df['RMSE_Moments'].min():.3f} - {df.loc[df['RMSE_Moments'].idxmin(), ['Alpha', 'Beta', 'Gamma']].to_dict()}")
    print(f"Best R2_Moments: {df['R2_Moments'].max():.3f} - {df.loc[df['R2_Moments'].idxmax(), ['Alpha', 'Beta', 'Gamma']].to_dict()}")
    print(f"Best RMSE_Excitations: {df['RMSE_Excitations'].min():.3f} - {df.loc[df['RMSE_Excitations'].idxmin(), ['Alpha', 'Beta', 'Gamma']].to_dict()}")
    print(f"Best R2_Excitations: {df['R2_Excitations'].max():.3f} - {df.loc[df['R2_Excitations'].idxmax(), ['Alpha', 'Beta', 'Gamma']].to_dict()}")
    
    # calculate overall best as sum of ranks
    df['RMSE_Sum'] = df['RMSE_Moments'] + df['RMSE_Excitations']
    df['R2_Sum'] = df['R2_Moments'] + df['R2_Excitations']
    
    # 1. Create a rank for RMSE_Sum (lower is better, so rank 1 is the lowest sum)
    df['Rank_RMSE'] = df['RMSE_Sum'].rank(ascending=True)

    # 2. Create a rank for R2_Sum (higher is better, so rank 1 is the highest sum)
    df['Rank_R2'] = df['R2_Sum'].rank(ascending=False)

    # 3. Combine ranks. The best row will have the lowest total rank (e.g., 1 + 1 = 2)
    df['Overall_Rank'] = df['Rank_RMSE'] + df['Rank_R2']
    df_sorted = df.sort_values(by='Overall_Rank')
    
    print("Top 5 best combinations based on low RMSE_Sum and high R2_Sum:\n")
    print(df_sorted[['Alpha', 'Beta', 'Gamma', 'RMSE_Sum', 'R2_Sum', 'Overall_Rank']].head())

    # Get the single best row
    best_combination = df_sorted.iloc[0]

    print("\n--------------------------------------------------")
    print("Best overall combination:")
    print(f"  Alpha: {best_combination['Alpha']}")
    print(f"  Beta: {best_combination['Beta']}")
    print(f"  Gamma: {best_combination['Gamma']}")
    print(f"  Combined RMSE (Sum): {best_combination['RMSE_Sum']:.2f}")
    print(f"  Combined R2 (Sum): {best_combination['R2_Sum']:.2f}")
    print("--------------------------------------------------")

    # add title with best iteration settings
    fig.suptitle(f"Best Overall - Alpha: {int(best_combination['Alpha'])}, Beta: {int(best_combination['Beta'])}, Gamma: {int(best_combination['Gamma'])}\nCombined RMSE: {best_combination['RMSE_Sum']:.2f}, Combined R²: {best_combination['R2_Sum']:.2f}", fontsize=16)    
    
    plt.tight_layout()
    savepath = CSVresultsPath.replace('.csv', '.png')
    plt.savefig(savepath)
    print(f"Parameter effects plot saved to: {savepath}")


def plot_ceinms_model_parameters(ceinmsModelPath=None):

    if not ceinmsModelPath:
        ceinmsModelPath = input("Enter path to optimised CEINMS model file: ").strip('"')

    def load_mtuSet(modelPath):
        root = ET.parse(modelPath).getroot()
        mtus = root.find('mtuSet').findall('mtu')
        
        # turn into DataFrame
        columns  = []
        for col in mtus[0].findall('*'): columns.append(col.tag)
        
        df = pd.DataFrame()
        for mtu in mtus:    
            name = mtu.find('name').text
            for col in columns:
                if col == 'name': continue
                if col not in df.columns:
                    df[col] = []
            for col in columns:
                if col == 'name': continue
                df.at[name, col] = float(mtu.find(col).text)
        
        return df

    mtuSet = load_mtuSet(ceinmsModelPath)
    muscle_names = mtuSet.index.tolist()
    parameters = mtuSet.columns.tolist()
    if len(parameters) == 10:    n_cols = 5
    else:                        n_cols = 4
    
    n_rows = (len(parameters) + n_cols - 1) // n_cols
    fig, axs = plt.subplots(n_rows, n_cols, figsize=(10, n_rows*3))
    plt.suptitle(f'Optimised Muscle Parameters: {ceinmsModelPath}', fontsize=16)
    axs = axs.flatten()

    for i, param in enumerate(parameters):
        
        # convert to numeric
        mtuSet[param] = pd.to_numeric(mtuSet[param], errors='coerce')   
        
        # plot bars left leg in red and right leg in blue
        colors = ['red' if name.endswith('_l') else 'blue' for name in muscle_names]
        axs[i].bar(muscle_names, mtuSet[param], color=colors)
        axs[i].set_title(param)
        axs[i].tick_params(axis='x', labelrotation=90)
        
    # set legend left leg on top right leg on bottom
    red_patch = plt.Line2D([0], [0], color='red', lw=4, label='Left Leg')
    blue_patch = plt.Line2D([0], [0], color='blue', lw=4, label='Right Leg')
    plt.legend(handles=[red_patch, blue_patch], loc='upper right')

    # make figure fullsize and tight layout
    plt.gcf().set_size_inches(18, 10)
    plt.tight_layout()
    
    # save figure
    fig_path = ceinmsModelPath.replace('.xml', '_parameters.png')
    plt.savefig(fig_path)
    print(f"Muscle parameters plot saved to: {fig_path}")


def plot_compare_ceinms_models(uncalibratedModelPath=None, calibratedModelPath=None):
    ''' Plot comparison of muscle parameters between uncalibrated and calibrated CEINMS models 
    
    Output: 
    - Bar plots of each muscle parameter for uncalibrated vs calibrated models
    - Difference in optimal fibre length, pennation angle, and tendon slack length between calibrated and uncalibrated models

    '''
    
    def load_mtuSet(modelPath):
        root = ET.parse(modelPath).getroot()
        mtus = root.find('mtuSet').findall('mtu')
        
        # turn into DataFrame
        columns  = []
        for col in mtus[0].findall('*'): columns.append(col.tag)
        
        df = pd.DataFrame()
        for mtu in mtus:    
            name = mtu.find('name').text
            for col in columns:
                if col == 'name': continue
                if col not in df.columns:
                    df[col] = []
            for col in columns:
                if col == 'name': continue
                df.at[name, col] = float(mtu.find(col).text)
        
        return df

    if not uncalibratedModelPath:
        uncalibratedModelPath = input("Enter path to uncalibrated CEINMS model file: ").strip('"')
    
    if not calibratedModelPath:
        calibratedModelPath = input("Enter path to calibrated CEINMS model file: ").strip('"')
        
    
    mtuSet_uncalibrated = load_mtuSet(uncalibratedModelPath)
    mtuSet_calibrated = load_mtuSet(calibratedModelPath)
    
    muscle_names = mtuSet_uncalibrated.index.tolist()
    parameters = mtuSet_uncalibrated.columns.tolist()
    
    if len(parameters) == 10:    n_cols = 5
    else:                        n_cols = 4
    
    n_rows = (len(parameters) + n_cols - 1) // n_cols
    fig, axs = plt.subplots(n_rows, n_cols, figsize=(10, n_rows*3))
    
    
    plt.suptitle(f'Compare: uncalibrated vs calibrated', fontsize=16)
    axs = axs.flatten()

    for i, param in enumerate(parameters):
        
        # convert to numeric
        mtuSet_uncalibrated[param] = pd.to_numeric(mtuSet_uncalibrated[param], errors='coerce')   
        mtuSet_calibrated[param] = pd.to_numeric(mtuSet_calibrated[param], errors='coerce')
        
        # plot bars left leg in red and right leg in blue
        colors = ['red' if name.endswith('_l') else 'blue' for name in muscle_names]
        if param in ['optimalFibreLength', 'pennationAngle', 'tendonSlackLength']:
            diff = mtuSet_calibrated[param] - mtuSet_uncalibrated[param]
            axs[i].bar(muscle_names, diff, color=colors)
            axs[i].set_title(f'Difference in {param} (Calibrated - Uncalibrated)')
            axs[i].tick_params(axis='x', labelrotation=90)
        else:            
            axs[i].bar(muscle_names, mtuSet_calibrated[param], color=colors)
            axs[i].set_title(param)
            axs[i].tick_params(axis='x', labelrotation=90)
            
    # set legend left leg on top right leg on bottom
    red_patch = plt.Line2D([0], [0], color='red', lw=4, label='Left Leg')
    blue_patch = plt.Line2D([0], [0], color='blue', lw=4, label='Right Leg')
    plt.legend(handles=[red_patch, blue_patch], loc='upper right')

    # make figure fullsize and tight layout
    plt.gcf().set_size_inches(18, 10)
    plt.tight_layout()
    
    # save figure
    fig_path = calibratedModelPath.replace('.xml', '_vs_uncalibrated.png')
    plt.savefig(fig_path)
    print(f"Muscle parameters plot saved to: {os.path.abspath(fig_path)}")


def plot_moments_calibration_results(momentResultsCSV=None):
    
    if not momentResultsCSV:
        momentResultsCSV = input("Enter path to moment calibration results CSV file: ").strip('"')

    moments_df = utils.load_any_data_file(momentResultsCSV)
    columns = moments_df.columns.tolist()
    data_columns = [col for col in columns if col != 'time']
    data_columns.sort()
    
    # get dof names by removing '_id' from id_columns
    dof_pairs = []
    for col in data_columns:
        moment_col = col + '_id'
        if moment_col in data_columns:
            dof_pairs.append((col, moment_col))

    n_dofs = len(dof_pairs)
    ncols = 2  # 2 columns for better layout
    nrows = int(np.ceil(n_dofs / ncols))
    
    # Create the figure and subplots (size from PlottingSettings.scale_per_subplot)
    fig, axes = plt.subplots(nrows, ncols, figsize=utils.fig_size(nrows, ncols))
    if n_dofs == 1:
        axes = [axes]
    elif nrows == 1:
        axes = axes.reshape(1, -1)
    axes = axes.flatten()
    
    # Plot each DOF pair
    for i, (dof, dof_id) in enumerate(dof_pairs):
        ax = axes[i]
        
        # Styling comes from the central scheme (utils.plot_style / settings.PlottingSettings).
        _c = utils.plot_style('ceinms'); _i = utils.plot_style('inverse_dynamics')
        line1 = ax.plot(moments_df['time'], moments_df[dof],
                        color=_c['color'], ls=_c['ls'], linewidth=_c['lw'], label='CEINMS')
        line2 = ax.plot(moments_df['time'], moments_df[dof_id],
                        color=_i['color'], ls=_i['ls'], linewidth=_i['lw'], label='inverse dynamics')

        # Set labels and title
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Moment (Nm)')
        ax.set_title(dof)
        ax.tick_params(axis='y')
        ax.grid(True, alpha=0.3)
        
        # Add legend (only on first subplot to avoid clutter)
        if i == 0:
            lines = line1 + line2
            labels = [l.get_label() for l in lines]
            ax.legend(lines, labels, loc='upper right')
    
    # Hide any unused subplots
    for i in range(n_dofs, len(axes)):
        axes[i].set_visible(False)
    
    # Adjust layout
    plt.tight_layout()
    plt.suptitle('DOF Angles and Moments Comparison', fontsize=16, y=1.02)
    
    # Save the figure
    savePath = momentResultsCSV.replace('.csv', '.png')
    plt.savefig(savePath, dpi=300, bbox_inches='tight')
    print(f"DOF comparison plot saved as '{savePath}'")

    return fig, axes, dof_pairs


def plot_ceinms_calibration_results(setupXML_path=None):

    if not setupXML_path:
        setupXML_path = input("Enter path to calibration setup XML file: ").strip('"')

    setupXML = ET.parse(setupXML_path).getroot()
    calibrationOutputDir = setupXML.find('outputDirectory').text
    calibrationOutputDir = os.path.join(os.path.dirname(setupXML_path), calibrationOutputDir)

    # find all files ending with _calibrationResults.sto
    result_files = os.listdir(calibrationOutputDir)
    result_files = [os.path.join(calibrationOutputDir, f) for f in result_files if f.endswith('.csv')]
    for result_file in result_files:
        data = utils.load_any_data_file(result_file)

        time_col = 'time' if 'time' in data.columns else data.columns[0]
        signal_names = [col for col in data.columns if col != time_col]

        if not signal_names:
            print(f"No signal columns found in {result_file}, skipping.")
            continue

        ncols = min(4, len(signal_names))
        nrows = int(np.ceil(len(signal_names) / ncols))
        fig, axs = plt.subplots(nrows, ncols, figsize=(ncols * 4, nrows * 3), squeeze=False)
        axs_flat = axs.flatten()

        plt.suptitle(f'Calibration Results: {os.path.basename(result_file)}', fontsize=14)
        for i, signal in enumerate(signal_names):
            axs_flat[i].plot(data[time_col], data[signal])
            axs_flat[i].set_title(signal, fontsize=9)
            axs_flat[i].set_xlabel('Time')

        # hide unused subplots
        for j in range(len(signal_names), len(axs_flat)):
            axs_flat[j].set_visible(False)

        plt.tight_layout()

        # save figure
        fig_path = result_file.replace('.csv', '.png')
        plt.savefig(fig_path, dpi=150, bbox_inches='tight')
        print(f"Calibration results plot saved to: {fig_path}")
        plt.close()


def plot_optimisation_results(optimisationOutputDir=None):

    if not optimisationOutputDir:
        optimisationOutputDir = input("Enter path to optimisation output directory: ").strip('"')

    # find all files ending with _optimisationResults.sto
    result_files = os.listdir(optimisationOutputDir)
    result_files = [os.path.join(optimisationOutputDir, f) for f in result_files if f.endswith('.sto')]
    muscleGroups = settings.BatchSettings.MUSCLE_GROUPS
    for result_file in result_files:
        data = utils.load_any_data_file(result_file)
        
        muscle_names = [col for col in data.columns if col != 'time']

        n_muscle_groups = len(muscleGroups)
        fig, axs = plt.subplots(n_muscle_groups, 1, figsize=(10, n_muscle_groups*3))
        plt.suptitle(f'Optimisation Results: {os.path.basename(result_file)}', fontsize=16)
        for i, (muscle_group, muscles) in enumerate(muscleGroups.items()):
            ax = axs[i] if n_muscle_groups > 1 else axs
            for muscle in muscles:
                if muscle in muscle_names:
                    ax.plot(data['time'], data[muscle], label=muscle)
            ax.set_title(f'Optimisation Results for Muscle Group: {muscle_group}')
            
            # if not last subplot, remove x labels
            if i < n_muscle_groups - 1:
                ax.set_xticklabels([])
            else:
                ax.set_xlabel('Time (%)')
                
            if ax.get_legend_handles_labels()[0]:
                ax.legend()

        
        # save figure
        fig_path = result_file.replace('.sto', '.png')
        plt.savefig(fig_path)
        print(f"Optimisation results plot saved to: {fig_path}")
        plt.close()


def plot_experimental_vs_ceinms(emgFile=None,        
                                ceinmsExcitationsFile=None,excitationGeneratorFile=None,externalMomentsFile=None, ceinmsTorquesFile=None):

    if not emgFile:
        emgFile = input("Enter path to EMG data file: ").strip('"')

    if not ceinmsExcitationsFile:
        ceinmsExcitationsFile = input("Enter path to CEINMS excitations file: ").strip('"')
    
    if not excitationGeneratorFile:
        excitationGeneratorFile = input("Enter path to excitation generator file: ").strip('"')
    
    if not externalMomentsFile:
        externalMomentsFile = input("Enter path to external moments data file: ").strip('"')

    if not ceinmsTorquesFile:
        ceinmsTorquesFile = input("Enter path to CEINMS torques data file: ").strip('"')

    emg_data = utils.load_any_data_file(emgFile)
    ceinms_data = utils.load_any_data_file(ceinmsExcitationsFile)
    
    ceinms_time_range  = [ceinms_data['time'].iloc[0],ceinms_data['time'].iloc[-1]]
    emg_data = emg_data[(emg_data['time'] >= ceinms_time_range[0]) & (emg_data['time'] <= ceinms_time_range[1])]
    
    emg_time_range  = [emg_data['time'].iloc[0],emg_data['time'].iloc[-1]]

    # time normalise both datasets to the same length
    emg_data = utils.time_normalise_df(emg_data)
    ceinms_data = utils.time_normalise_df(ceinms_data)
    
    emg_mapping = ET.parse(excitationGeneratorFile).getroot().find('mapping')

    muscle_mapping = {}
    for excitation in emg_mapping.findall('excitation'):
        muscle_id = excitation.get('id')
        input_elems = excitation.findall('input')
        if len(input_elems) > 0:
            for input_elem in input_elems:
                signal = input_elem.text
                if signal not in muscle_mapping:
                    muscle_mapping[signal] = []
                muscle_mapping[signal].append(muscle_id)
    
    # -- Plot EMG vs CEINMS excitations -- #     
    n_muscles = len(muscle_mapping)
    fig, axs = plt.subplots(n_muscles, 1, figsize=(10, n_muscles*3))
    plt.suptitle(f'EMG vs CEINMS Excitations', fontsize=16)
    for i, (signal, muscles) in enumerate(muscle_mapping.items()):
        ax = axs[i] if n_muscles > 1 else axs
        line_emg = ax.plot(emg_data['time'], emg_data[signal], label=signal, color='blue')
        lines_ceinms = []   
        lineStyles = ['-', '--', '-.', ':','-', '--', '-.', ':']
        for j, muscle in enumerate(muscles):
            if muscle in ceinms_data.columns:
                r2 = utils.rsquared(emg_data[signal], ceinms_data[muscle])
                range_signal = emg_data[signal].max() - emg_data[signal].min()
                rmse = utils.rmse(emg_data[signal], ceinms_data[muscle])
                rmse_percent = (rmse / range_signal) * 100 if range_signal != 0 else 0
                lines_ceinms.append(ax.plot(ceinms_data['time'],ceinms_data[muscle], 
                                            linestyle=lineStyles[j % len(lineStyles)],
                                            label=f'{muscle} (R²: {r2:.2f}, RMSE: {rmse:.2f}/{rmse_percent:.0f}%)', color='red'))
                ax.set_ylabel('Excitation')
                if i < n_muscles - 1:
                    ax.set_xticklabels([])
                else:
                    ax.set_xlabel('Time (%)')
            else:
                print(f"Muscle {muscle} not found in CEINMS excitations data.")
        
        # legend with all lines
        handles = [line_emg[0]] + [line[0] for line in lines_ceinms]
        labels = [signal] + [f'{muscle} (R²: {utils.rsquared(emg_data[signal], ceinms_data[muscle]):.2f}, RMSE: {utils.rmse(emg_data[signal], ceinms_data[muscle]):.2f})' for muscle in muscles if muscle in ceinms_data.columns]
        ax.legend(handles, labels)
    
    # save figure
    ext = os.path.splitext(ceinmsExcitationsFile)[1]
    fig_path = ceinmsExcitationsFile.replace(ext, 'vs_emg.png')
    plt.savefig(fig_path)
    print(f"EMG vs CEINMS excitations plot saved to: {fig_path}")
    plt.close()

    # -- Plot external moments vs CEINMS torques -- #
    
    ext_moments_data = utils.load_any_data_file(externalMomentsFile)
    ceinms_torques_data = utils.load_any_data_file(ceinmsTorquesFile)
    
    # allign times and time normalise
    time_range_torques  = [ceinms_torques_data['time'].iloc[0],ceinms_torques_data['time'].iloc[-1]]
    ext_moments_data = ext_moments_data[(ext_moments_data['time'] >= time_range_torques[0]) & (ext_moments_data['time'] <= time_range_torques[1])]

    ext_moments_data = utils.time_normalise_df(ext_moments_data)
    ceinms_torques_data = utils.time_normalise_df(ceinms_torques_data)

    dof_names = [col for col in ceinms_torques_data.columns if col != 'time']
    
    n_dofs = len(dof_names)
    fig, axs = plt.subplots(n_dofs, 1, figsize=(10, n_dofs*3))
    plt.suptitle(f'External Torques vs CEINMS Torques', fontsize=16)
    
    for i, dof in enumerate(dof_names):
        ax = axs[i] if n_dofs > 1 else axs
        r2 = utils.rsquared(ext_moments_data[dof + '_moment'], ceinms_torques_data[dof])
        range_moments = ext_moments_data[dof + '_moment'].max() - ext_moments_data[dof + '_moment'].min()        
        rmse = utils.rmse(ext_moments_data[dof + '_moment'], ceinms_torques_data[dof])
        rmse_percent = (rmse / range_moments) * 100 if range_moments != 0 else 0
        line_ext = ax.plot(ext_moments_data[dof + '_moment'], label=f'External Moment', color='blue')
        line_cei = ax.plot(ceinms_torques_data[dof], label=f'CEINMS Torque (R²: {r2:.2f}, RMSE: {rmse:.2f}/{rmse_percent:.0f}%)', color='red')
        ax.set_title(f'{dof}')
        ax.set_ylabel('Moment (Nm)')
        if i < n_dofs - 1:
            ax.set_xticklabels([])
        else:
            ax.set_xlabel('Time (%)')
        ax.legend()
    
    ext = os.path.splitext(ceinmsTorquesFile)[1]
    fig_path = ceinmsTorquesFile.replace(ext, 'vs_external_torques.png')
    plt.savefig(fig_path)
    print(f"External torques vs CEINMS torques plot saved to: {fig_path}")
    plt.close()


def plot_ceinms_muscle_forces(ceinmsForcesFile=None):

    if not ceinmsForcesFile:
        ceinmsForcesFile = input("Enter path to CEINMS muscle forces file: ").strip('"')

    ceinms_forces = utils.load_any_data_file(ceinmsForcesFile)
    ceinms_activations = utils.load_any_data_file(ceinmsForcesFile.replace('MuscleForces', 'Activations'))
    ceinms_fibre_lengths = utils.load_any_data_file(ceinmsForcesFile.replace('MuscleForces', 'FibreLengths'))
    
    muscle_names = [col for col in ceinms_forces.columns if col != 'time']

    n_muscles = len(muscle_names)
    if n_muscles == 0:
        print("No muscle columns found in CEINMS forces file.")
        return
    
    n_cols = int(np.ceil(np.sqrt(n_muscles)))
    n_rows = int(np.ceil(n_muscles / n_cols))

    fig, axs = plt.subplots(n_rows, n_cols, figsize=(n_cols * 4, n_rows * 3))
    plt.suptitle('CEINMS Muscle Forces', fontsize=16)

    # Normalize axs to 1D array for easy indexing
    if isinstance(axs, np.ndarray):
        axs_flat = axs.flatten()
    else:
        axs_flat = np.array([axs])

    for i, muscle in enumerate(muscle_names):
        ax = axs_flat[i]
        ax.plot(ceinms_forces['time'], ceinms_forces[muscle], label=muscle, color='green', linewidth=1.5)

        # add activations on secondary y-axis
        ax2 = ax.twinx()
        if muscle in ceinms_activations.columns:
            ax2.plot(ceinms_activations['time'], ceinms_activations[muscle], label=f'{muscle} Activation', color='gray', alpha=0.6, linewidth=3)
            ax2.set_ylabel('Activation')

        ax.set_title(muscle)
        ax.set_ylabel('Force (N)')
        # Only the bottom row gets x labels
        row = i // n_cols
        if row < n_rows - 1:
            ax.set_xticklabels([])
        else:
            ax.set_xlabel('Time (%)')
        # create simple legend with generic labels 'force' and 'activation'
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        h_force = h1[0] if h1 else None
        h_act = h2[0] if h2 else None
        legend_handles = [h for h in (h_force, h_act) if h is not None]
        legend_labels = ['force', 'activation'][:len(legend_handles)]
        if legend_handles:
            ax.legend(legend_handles, legend_labels, fontsize='small')

    # Hide any unused subplots
    for j in range(n_muscles, n_rows * n_cols):
        axs_flat[j].set_visible(False)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # save figure
    ext = os.path.splitext(ceinmsForcesFile)[1]
    fig_path = ceinmsForcesFile.replace(ext, '.png')
    plt.savefig(fig_path)
    print(f"CEINMS muscle forces plot saved to: {os.path.abspath(fig_path)}")
    plt.close()




# --------------------------------------------------------------------------- #
# Calibration summary: uncalibrated (open) vs calibrated (filled) per muscle
# group and side. Replaces the _parameters.png / _vs_uncalibrated.png bar
# charts in the calibration run (those functions are kept for old callers).
# --------------------------------------------------------------------------- #
CALIBRATION_GROUPS = [
    ("Gluteus maximus", ("glmax",)),
    ("Gluteus med+min", ("glmed", "glmin")),
    ("Adductors", ("add", "grac", "pect")),
    ("Hamstrings", ("bflh", "bfsh", "semimem", "semiten")),
    ("Rectus femoris", ("recfem",)),
    ("Vasti", ("vas",)),
    ("Iliopsoas", ("psoas", "iliacus")),
    ("Triceps surae", ("gas", "soleus")),
    ("Dorsiflexors", ("tibant", "edl", "ehl")),
]


def _read_mtus(path):
    root = ET.parse(path).getroot()
    rows = {}
    for mtu in root.find("mtuSet").findall("mtu"):
        rows[mtu.find("name").text] = {c.tag: float(c.text) for c in mtu
                                        if c.tag != "name" and _isfloat(c.text)}
    return pd.DataFrame.from_dict(rows, orient="index")


def _isfloat(s):
    try:
        float(s); return True
    except (TypeError, ValueError):
        return False


def _group_table(df):
    """Per side x group: mean Lopt/Lts (mm), sum Fmax*strength (N), mean strength."""
    df = df.copy()
    df["Fmax_eff"] = df["maxIsometricForce"] * df.get("strengthCoefficient", 1.0)
    out = []
    for side in ("r", "l"):
        for g, keys in CALIBRATION_GROUPS:
            sel = df[[n.endswith("_" + side) and n.startswith(keys) for n in df.index]]
            if sel.empty:
                continue
            row = dict(side=side.upper(), group=g,
                       Lopt=sel["optimalFibreLength"].mean() * 1000,
                       Lts=sel["tendonSlackLength"].mean() * 1000,
                       Fmax=sel["Fmax_eff"].sum(),
                       strength=sel.get("strengthCoefficient", pd.Series([1.0])).mean())
            for k in ("c1", "c2", "shapeFactor"):
                if k in sel:
                    row[k] = sel[k].mean()
            out.append(row)
    return pd.DataFrame(out)


def plot_calibration_parameters(uncalibratedModelPath, calibratedModelPath, out_png=None,
                                title=None):
    """Dumbbell figure: open = uncalibrated, filled = calibrated, one x slot per
    side x muscle group. Writes <calibrated dir>/calibration_parameters.png and a
    matching .csv (per-muscle values, both models)."""
    u, c = _read_mtus(uncalibratedModelPath), _read_mtus(calibratedModelPath)
    gu, gc = _group_table(u), _group_table(c)
    out_png = out_png or os.path.join(os.path.dirname(os.path.abspath(calibratedModelPath)),
                                      "calibration_parameters.png")
    panels = [("Lopt", "(a) optimal fibre length", "L$_{opt}$ (mm)"),
              ("Lts", "(b) tendon slack length", "L$_{slack}$ (mm)"),
              ("Fmax", "(c) max isometric force x strength coefficient (group sum)", "F$_{max}$ (N)"),
              ("strength", "(d) strength coefficient (group mean)", "strength coef. (-)")]
    shape = [k for k in ("c1", "c2", "shapeFactor") if k in gc]
    if shape:
        panels.append(("shape", "(e) activation dynamics (group mean): c1, c2, shape factor", "value (-)"))
    col = {"R": "#0072B2", "L": "#D55E00"}
    x = np.arange(len(gc))
    fig, axs = plt.subplots(len(panels), 1, figsize=(max(12, 0.75 * len(x)), 2.6 * len(panels)),
                            sharex=True)
    for ax, (key, ttl, yl) in zip(np.atleast_1d(axs), panels):
        if key == "shape":
            for j, (k, dx, mk) in enumerate(zip(shape, (-0.2, 0, 0.2), ("o", "s", "^"))):
                for i in x:
                    s = gc.side[i]
                    ax.plot([i + dx] * 2, [gu[k][i], gc[k][i]], color=col[s], lw=1.2)
                    ax.scatter(i + dx, gu[k][i], s=40, facecolor="white", edgecolor=col[s], marker=mk, zorder=3)
                    ax.scatter(i + dx, gc[k][i], s=25, color=col[s], marker=mk, zorder=3,
                               label=k if (i == 0) else None)
            ax.legend(fontsize=7, loc="upper right", ncol=3)
        else:
            for i in x:
                s = gc.side[i]
                ax.plot([i, i], [gu[key][i], gc[key][i]], color=col[s], lw=1.5)
                ax.scatter(i, gu[key][i], s=55, facecolor="white", edgecolor=col[s], lw=1.5, zorder=3)
                ax.scatter(i, gc[key][i], s=35, color=col[s], zorder=3)
            if key == "strength":
                ax.axhline(1, color="grey", lw=0.8, ls=":")
        ax.set_title(ttl, fontsize=10)
        ax.set_ylabel(yl)
        ax.grid(axis="y", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s} {g}" for s, g in zip(gc.side, gc.group)], rotation=35, ha="right", fontsize=8)
    handles = [plt.Line2D([], [], marker="o", ls="", mfc="white", mec="k", label="uncalibrated"),
               plt.Line2D([], [], marker="o", ls="", color="k", label="calibrated"),
               plt.Line2D([], [], color=col["R"], lw=3, label="right"),
               plt.Line2D([], [], color=col["L"], lw=3, label="left")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False)
    fig.suptitle(title or "CEINMS calibration - muscle-tendon parameters, uncalibrated vs calibrated\n"
                 + os.path.dirname(os.path.abspath(calibratedModelPath)), fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    u.add_suffix("_uncal").join(c.add_suffix("_cal")).to_csv(out_png.replace(".png", ".csv"))
    print(f"Calibration parameters plot saved to: {out_png}")
    return out_png


#: muscle -> stack-group colour, the same colours as the JCF stack figures
#: (Charite tests/actuators_so/plot.py STACK_COLORS) -- 2026-10-21
_SUMMARY_GROUPS = [("Adductors", ("addbrev", "addlong", "addmag"), "#2bb5c0"),
                   ("Gluteus maximus", ("glmax",), "#a266b1"),
                   ("Gluteus med+min", ("glmed", "glmin"), "#5d8cb3"),
                   ("Hamstrings", ("bflh", "bfsh", "semimem", "semiten"), "#6b2f73"),
                   ("Iliopsoas", ("iliacus", "psoas"), "#dd7036"),
                   ("Rectus femoris", ("recfem",), "#2f6b43"),
                   ("Gastrocnemius", ("gaslat", "gasmed"), "#a41e23"),
                   ("Soleus", ("soleus",), "#e8787b"),
                   ("Vasti", ("vasint", "vaslat", "vasmed"), "#6cc070")]


def _muscle_colour(m, default="0.45"):
    m = str(m).lower()
    for _, pres, col in _SUMMARY_GROUPS:
        if m.startswith(pres):
            return col
    return default


def plot_ceinms_summary(outputDirectory, setupXML_path, save_name="summary.png", n_major=6):
    """<outputDirectory>/summary.png (2026-10-21), one ROW PER DOF (CEINMS dofSet
    + subtalar when its moment arms exist), four columns:

      1  ID moment (black), CEINMS torque (red) and the muscle moments
         (force x moment arm) stacked by muscle group underneath
      2  CEINMS activation of the major muscles crossing that DOF (solid) and
         their measured EMG where a channel drives them (dotted, same colour)
      3  normalised fibre length of the same muscles
      4  their moment arm about that DOF (cm)

    "Major" = the `n_major` muscles with the largest peak |F*r| at the DOF,
    among those crossing it (|r| > 1 mm). Colours = muscle group (as the JCF
    stacks); line style separates muscles of one group. x = % CEINMS window."""
    import numpy as _np
    setupXML_path = os.path.abspath(setupXML_path)
    base = os.path.dirname(setupXML_path)
    _a = lambda p: p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
    out = _a(outputDirectory)
    setup = ET.parse(setupXML_path).getroot()
    inp_path = _a(setup.find("inputDataFile").text)
    inp = ET.parse(inp_path).getroot()
    _ai = lambda p: p if os.path.isabs(p) else os.path.normpath(os.path.join(os.path.dirname(inp_path), p))

    def _load(p):
        return utils.load_any_data_file(p) if p and os.path.exists(p) else None

    tor = _load(os.path.join(out, "Torques.sto"))
    frc = _load(os.path.join(out, "MuscleForces.sto"))
    if tor is None or frc is None:
        print(f"[summary] skipped: no Torques/MuscleForces in {out}")
        return None
    t0, t1 = float(tor["time"].iloc[0]), float(tor["time"].iloc[-1])

    def _norm(df):
        if df is None:
            return None
        d = df[(df["time"] >= t0 - 1e-9) & (df["time"] <= t1 + 1e-9)]
        return utils.time_normalise_df(d) if len(d) > 1 else None

    tor, frc = _norm(tor), _norm(frc)
    act = _norm(_load(os.path.join(out, "Activations.sto")))
    nfl = _norm(_load(os.path.join(out, "NormFibreLengths.sto")))
    emg = _norm(_load(_ai(inp.find("excitationsFile").text)))
    idm = _norm(_load(_ai(inp.find("externalTorquesFile").text)))
    x = _np.linspace(0, 100, 101)

    # muscle -> EMG channel (excitation generator)
    eg = ET.parse(_a(setup.find("excitationGeneratorFile").text)).getroot().find("mapping")
    m2ch = {}
    for e in eg.findall("excitation"):
        ins = [i_.text for i_ in e.findall("input")]
        if ins and emg is not None and ins[0] in emg.columns:
            m2ch[e.get("id")] = ins[0]
    # moment arms per DOF (+ subtalar from the same muscle_analysis folder)
    ma_files = {}
    maf = inp.find("momentArmsFiles")
    for f in (maf.findall("momentArmsFile") if maf is not None else []):
        ma_files[f.get("dofName")] = _ai(f.text)
    if ma_files:
        _d = os.path.dirname(next(iter(ma_files.values())))
        for sd in ("r", "l"):
            p = os.path.join(_d, f"_MuscleAnalysis_MomentArm_subtalar_angle_{sd}.sto")
            if os.path.exists(p):
                ma_files.setdefault(f"subtalar_angle_{sd}", p)
    # rows = the DOFs this run TRACKED (execution/optimise cfg dofSet), so a
    # one-leg run shows one leg (2026-10-22); fall back to the torque columns
    dofs = []
    try:
        _cfg = ET.parse(_a(setup.find("executionFile").text)).getroot()
        _ds = _cfg.find(".//dofSet")
        dofs = (_ds.text or "").split() if _ds is not None else []
    except Exception:
        dofs = []
    if not dofs:
        dofs = [c for c in tor.columns if c != "time"]
        # + subtalar of the side(s) shown, when its moment arms exist
        _sides = {d_[-1] for d_ in dofs}
        dofs += [d for d in ma_files if d not in dofs and d.startswith("subtalar") and d[-1] in _sides]
    mas = {d: _norm(_load(p)) for d, p in ma_files.items()}

    groups = [g for g, _, _ in _SUMMARY_GROUPS] + ["Other muscles"]
    gcol = {g: c for g, _, c in _SUMMARY_GROUPS}
    gcol["Other muscles"] = "0.75"

    def _grp(m):
        m_ = str(m).lower()
        for g, pres, _ in _SUMMARY_GROUPS:
            if m_.startswith(pres):
                return g
        return "Other muscles"

    ls = ["-", "--", "-.", ":"]
    nr = len(dofs)
    fig, ax = plt.subplots(nr, 4, figsize=(22, 2.2 * nr + 1.4), squeeze=False, sharex=True)
    for c, ttl in enumerate(["moment (N·m): ID, CEINMS, muscle groups",
                             "activation (solid) / EMG (dotted)",
                             "normalised fibre length", "moment arm (cm)"]):
        ax[0][c].set_title(ttl, fontsize=11, fontweight="bold")
    used = set()
    for r, dof in enumerate(dofs):
        d = mas.get(dof)
        mus = [m for m in frc.columns if m != "time" and d is not None and m in d.columns
               and _np.nanmax(_np.abs(d[m].to_numpy(float))) > 1e-3]
        mom = {m: frc[m].to_numpy(float) * d[m].to_numpy(float) for m in mus}
        # (1) moments: group stack + ID + CEINMS
        a = ax[r][0]
        pos, neg = _np.zeros_like(x), _np.zeros_like(x)
        for g in groups:
            v = sum((mom[m] for m in mus if _grp(m) == g), _np.zeros_like(x))
            if not _np.any(_np.abs(v) > 1e-6):
                continue
            used.add(g)
            p_, n_ = _np.clip(v, 0, None), _np.clip(v, None, 0)
            a.fill_between(x, pos, pos + p_, color=gcol[g], lw=0, alpha=0.85)
            a.fill_between(x, neg, neg + n_, color=gcol[g], lw=0, alpha=0.85)
            pos, neg = pos + p_, neg + n_
        col = dof + "_moment"
        # reserve (2026-10-22): the <dof>_reserve column bioscout adds to the CEINMS
        # forces for the JRA (= ID - CEINMS muscle moment); else that gap itself
        _rc = f"{dof}_reserve"
        if _rc in frc.columns:
            res = frc[_rc].to_numpy(float)
        elif idm is not None and col in idm.columns:
            res = idm[col].to_numpy(float) - sum(mom.values(), _np.zeros_like(x))
        else:
            res = None
        if res is not None and _np.any(_np.abs(res) > 1e-6):
            p_, n_ = _np.clip(res, 0, None), _np.clip(res, None, 0)
            _kw = dict(facecolor="0.35", hatch="///", edgecolor="white", lw=0)
            a.fill_between(x, pos, pos + p_, **_kw)
            a.fill_between(x, neg, neg + n_, **_kw)
            _tot = _np.abs(res).sum() + _np.abs(sum(mom.values(), _np.zeros_like(x))).sum()
            a.text(0.02, 0.95, f"reserve {100 * _np.abs(res).sum() / max(_tot, 1e-12):.0f} %",
                   transform=a.transAxes, ha="left", va="top", fontsize=7)
            used.add("__reserve__")
        if idm is not None and col in idm.columns:
            a.plot(x, idm[col].to_numpy(float), color="k", lw=1.6, ls=(0, (4, 1.5)), label="ID")
        if dof in tor.columns:
            lab = "CEINMS"
            if idm is not None and col in idm.columns:
                lab += (f" R² {utils.rsquared(idm[col], tor[dof]):.2f}"
                        f" RMSE {utils.rmse(idm[col], tor[dof]):.1f}")
            a.plot(x, tor[dof].to_numpy(float), color="tab:red", lw=1.3, label=lab)
        a.axhline(0, color="0.6", lw=0.6)
        a.set_ylabel(dof, fontsize=9, fontweight="bold")
        a.legend(fontsize=6.5, frameon=False, loc="upper right")
        # major muscles at this DOF
        major = sorted(mus, key=lambda m: -_np.nanmax(_np.abs(mom[m])))[:n_major]
        k_in = {}
        for m in major:
            g = _grp(m)
            j = k_in.get(g, 0); k_in[g] = j + 1
            c_, l_ = gcol[g], ls[j % 4] if True else "-"
            if act is not None and m in act.columns:
                ax[r][1].plot(x, act[m].to_numpy(float), color=c_, ls=l_, lw=1.4, label=m)
            ch = m2ch.get(m)
            if ch:
                ax[r][1].plot(x, emg[ch].to_numpy(float), color=c_, ls=":", lw=1.1, alpha=0.8,
                              label=f"EMG {ch.replace('EMG_Channels_', '')}")
            if nfl is not None and m in nfl.columns:
                ax[r][2].plot(x, nfl[m].to_numpy(float), color=c_, ls=l_, lw=1.4, label=m)
            ax[r][3].plot(x, 100 * d[m].to_numpy(float), color=c_, ls=l_, lw=1.4, label=m)
        ax[r][2].axhspan(0.5, 1.5, color="0.95", zorder=0)
        ax[r][2].axhline(1.0, color="0.6", lw=0.6)
        ax[r][3].axhline(0, color="0.6", lw=0.6)
        for c in (1, 2, 3):
            ax[r][c].legend(fontsize=6, frameon=False, loc="upper right", ncol=2)
    for c in range(4):
        ax[nr - 1][c].set_xlabel("% CEINMS window")
    for a in ax.flat:
        a.tick_params(labelsize=7)
        a.spines[["top", "right"]].set_visible(False)
    from matplotlib.patches import Patch
    h = [Patch(color=gcol[g], label=g) for g in groups if g in used]
    if "__reserve__" in used:
        h.append(Patch(facecolor="0.35", hatch="///", edgecolor="white", label="Reserve actuators"))
    fig.legend(handles=h, loc="lower center", ncol=min(len(h), 10), frameon=False, fontsize=8)
    fig.suptitle(f"CEINMS summary — {os.path.basename(out)} (one row per DOF)", fontweight="bold")
    fig.tight_layout(rect=(0, 0.02, 1, 0.985))
    p = os.path.join(out, save_name)
    fig.savefig(p, dpi=120)
    plt.close(fig)
    print(f"[summary] -> {p}")
    return p
