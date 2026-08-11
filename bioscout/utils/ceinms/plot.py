"""bioscout.utils.ceinms.plot — Figures made from CEINMS output — calibration parameters, model
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


