"""
bioscout.utils.plot — the Plot class (multi-model comparison figures).
Extracted from utils/__init__.py.

Runtime-rebound names (settings, *_DIR, Analyse, openSim, ceinms) and the other
utils-level helpers are read through the live ``utils`` module (``_u``) so that
``Project``'s per-project rebinding still reaches them.
"""
import os
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from bioscout import utils as _u


class Plot():
    def __init__(self, session='25_03_31', trialName='Squat_bw_01', results_dir=_u.RESULTS_DIR):

        model_config = getattr(getattr(_u.settings, 'BatchSettings', None), 'model_config', {})

        self.trialName = trialName
        subject_names = {k: v['subject'] for k, v in model_config.items()}
        self.colors = {k: v['color'] for k, v in model_config.items()}
        self.forces_type = {k: v['force_type'] for k, v in model_config.items()}
        self.lineStyles = {k: v['line_style'] for k, v in model_config.items()}
        labels = list(model_config.keys())

        self.results_dir = results_dir       
        os.makedirs(self.results_dir, exist_ok=True)

        # self.trials is a dictionary that must contain an Analyse object for each trial to be plotted, with keys matching the labels in model_config
        self.trials = {}
        for label, subject in zip(labels, subject_names.values()):
            trialPath = os.path.join(_u.SIMULATIONS_DIR, subject, session, trialName)
            self.trials[label] = _u.Analyse(trialPath)

        print(f'Results to be saved to: {self.results_dir}')

    def _refresh_results_summary(self):
        """Keep the markdown summary in sync with generated output files."""
        self.write_results_markdown_summary(self.results_dir)

    def marker_error(self):
        '''
        Plots marker error for each trial on the provided axes.
        '''
        body_segments = _u.settings.marker_weights.keys()
        dofs = _u.settings.BatchSettings.dof_list


        for trial_name, trial in self.trials.items():
            if not isinstance(trial, _u.Analyse):
                continue

            marker_errors = _u.load_any_data_file('.\\_ik_marker_errors_all.sto')
            markers = trial.get_markers()
            for segment in body_segments:
                for dof in dofs:
                    col_name = f'{segment}_{dof}_error'
                    if col_name in marker_errors.columns:
                        plt.plot(marker_errors['time'], marker_errors[col_name], label=f'{trial_name} - {segment} {dof}', color=self.colors[trial_name], linestyle=self.lineStyles[trial_name])
                    else:
                        print(f"Column {col_name} not found in {trial_name} marker error data.")

    def external_biomechanics(self):

        ik_columns = _u.settings.BatchSettings.dof_list
        n_cols = len(ik_columns)
        n_rows = 2
        fig, ax = plt.subplots(nrows=int(n_rows), ncols=int(n_cols), figsize=(2*n_cols, 3*n_rows), sharex='col')
        plt.suptitle('Comparison', y=0.98, fontsize=10)

        models_to_flip = ['Lernagopal', 'Scaled (GPK)']  # Add model names that require flipping here
        models_to_flip = ['Lernagopal', 'GPK']

        for trial_name, trial in self.trials.items():
            angles = _u.load_any_data_file(os.path.join(trial.path, trial.ik))
            moments = _u.load_any_data_file(os.path.join(trial.path, trial.id)) 
            for col_idx, col_name in enumerate(ik_columns):
                
                if col_name == 'time':
                    continue
                
                if any(model in trial_name for model in models_to_flip) and col_name.__contains__('knee_angle'):
                    print(trial_name + '_ flipped') 
                    flip_values = -1
                else:
                    flip_values = 1
                
                try:
                    ax[0, col_idx].plot(angles['time'], angles[col_name] * flip_values, label=trial_name, color=self.colors[trial_name], linestyle=self.lineStyles[trial_name])
                    ax[1, col_idx].plot(moments['time'], moments[col_name+'_moment']* flip_values, label=trial_name, color=self.colors[trial_name], linestyle=self.lineStyles[trial_name])
                except KeyError:
                    print(f"Column {col_name} not found in {trial_name} data.")
                
                ax[0, col_idx].set_title(f'{col_name}', fontsize=8)
                ax[1, col_idx].set_xlabel('Time (s)')
                if col_idx == 0:
                    ax[0, col_idx].set_ylabel('Angle (deg)')
                    ax[1, col_idx].set_ylabel('Moment (Nm)')           
                
        # add legend outside of the plot        
        white_right_margin = 0.2
        handles, labels_legend = ax[0, 0].get_legend_handles_labels()
        plt.tight_layout()
        plt.subplots_adjust(right=1 - white_right_margin)
        fig.legend(handles, labels_legend, loc='center left', bbox_to_anchor=(1 - white_right_margin + 0.02, 0.5))

        save_path = os.path.join(self.results_dir, f'external_biomech_{self.trialName}.png')
        plt.savefig(save_path)
        print(f"Inverse kinematics comparison plot saved: {save_path}")
        self._refresh_results_summary()

    def muscle_moments(self):

        '''
        Plots muscle moments for a given degree of freedom (DOF) on the provided axes.
        Parameters:
            - ax: The matplotlib axes to plot on.
            - trial: The trial data containing paths to the necessary files.
            - dof: The degree of freedom for which to plot the muscle moments (e.g., 'hip_flexion_r').
            - forces: The type of muscle forces to use ('so' for static optimization or 'ceinms' for electromyography informed optimization).
        '''

        def create_muscle_moments_csv(trial: _u.Analyse, dof: str, forces: str = 'so'):

            output_csv_path = os.path.join(trial.path, f'muscle_moments_{dof}_{forces}.csv')

            if os.path.exists(output_csv_path):
                print(f"Muscle moments CSV already exists: {output_csv_path}")
                return pd.read_csv(output_csv_path)
            
            moments = _u.load_any_data_file(os.path.join(trial.path, trial.id))

            if forces.lower() == 'so':
                muscle_forces = _u.load_any_data_file(os.path.join(trial.path, trial.so_forces))
            elif forces.lower() == 'ceinms':
                muscle_forces = _u.load_any_data_file(os.path.join(trial.path, trial.jra_forces_ceinms))
            else:
                return

            ma_path = os.path.join(trial.path, trial.ma, f'_MuscleAnalysis_MomentArm_{dof}.sto')
            if not os.path.exists(ma_path):
                print(f"Moment arm file for {dof} not found in {trial.path}. Skipping muscle moment plot for this DOF.")
                return

            try:
                moment_arms = _u.load_any_data_file(ma_path)
            except Exception:
                print(f"Moment arm file for {dof} not found in {trial.path}. Skipping muscle moment plot for this DOF.")
                return

            muscle_list = muscle_forces.columns.drop('time')
            muscles = _u.openSim.find_non_zero_mom_arm_muscles(moment_arms, muscle_list)

            muscle_moments = muscle_forces.multiply(moment_arms, axis=0)
            muscle_moments['time'] = muscle_forces['time']

            
            muscle_moments.to_csv(output_csv_path, index=False)
            print(f"Muscle moments CSV created: {output_csv_path}")

            return muscle_moments

        def plot_muscle_moments(ax: plt.Axes, trial: _u.Analyse, dof: str, forces: str = 'so', model_name: str = '', flip: float = 1.0):

            muscle_moments = create_muscle_moments_csv(trial, dof, forces)
            if muscle_moments is None:
                return

            muscles = muscle_moments.columns.drop('time')
            moments = _u.load_any_data_file(os.path.join(trial.path, trial.id))

            id_col = dof + '_moment'
            if id_col not in moments.columns:
                ax.set_title(f'{dof}\n(no ID data)', fontsize=7)
                return

            # Plot individual muscle contributions
            for muscle in muscles:
                ax.plot(muscle_moments['time'], muscle_moments[muscle] * 1, label=muscle, linestyle='--')

            # Plot inverse dynamics moment
            ax.plot(moments['time'], moments[id_col] * 1,
                    label=f'Inverse Dynamics {model_name}',
                    color=self.colors.get(model_name, 'black'), linewidth=2)

            total_muscle_moment = muscle_moments[muscles].sum(axis=1)*1

            # Fill area under total muscle moment
            ax.fill_between(muscle_moments['time'], total_muscle_moment, alpha=0.3, color='gray')

            # Dashed outline of total muscle moment
            ax.plot(muscle_moments['time'], total_muscle_moment,
                    color='black', linestyle='--', linewidth=2, label='Total Muscle Moment')

            if trial.subject == 'Athlete_03' and dof == 'knee_angle_r':
                pass
                
            # Residual annotation
            inverse_dynamics_moment = moments[id_col] * flip
            moment_diff = total_muscle_moment - inverse_dynamics_moment
            moment_diff_mean = moment_diff.mean()
            moment_diff_std = moment_diff.std()
            mm_range = total_muscle_moment.max() - total_muscle_moment.min()
            moment_diff_mean_pct = (moment_diff_mean / mm_range) * 100 if mm_range != 0 else np.nan
            moment_diff_std_pct = (moment_diff_std / mm_range) * 100 if mm_range != 0 else np.nan

            text_str = (f'Mean Residual: {moment_diff_mean:.2f} Nm ({moment_diff_mean_pct:.2f}%)\n'
                        f'Std: {moment_diff_std:.2f} Nm ({moment_diff_std_pct:.2f}%)')
            ax.text(0.02, 0.98, text_str, transform=ax.transAxes, fontsize=6,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))


        _models_to_flip = ['Lernagopal', 'GPK']

        ik_columns = _u.settings.BatchSettings.dof_list
        n_rows = len(ik_columns)
        n_cols = len(self.trials)
        fig, axes = plt.subplots(nrows=n_rows, ncols=n_cols,
                                 figsize=(2 * n_cols, 3 * n_rows), sharex='col')

        for irow, dof in enumerate(ik_columns):
            for icol, model_name in enumerate(self.trials.keys()):
                ax = axes[irow, icol]
                flip = -1.0 if ('knee_angle' in dof and any(m in model_name for m in _models_to_flip)) else 1.0
                try:
                    plot_muscle_moments(ax, self.trials[model_name], dof,
                                        forces=self.forces_type[model_name],
                                        model_name=model_name,
                                        flip=flip)
                except Exception as e:
                    print(f"Error plotting muscle moments for {model_name}, {dof}: {e}")
                    print(f'check folder {self.trials[model_name].path} for missing files.')

                if icol == 0:
                    ax.set_ylabel(f'{dof} (Nm)')

                if irow == len(ik_columns) - 1:
                    ax.set_xlabel('Time (s)')
                elif irow == 0:
                    ax.set_title(f'{model_name}', fontsize=8)

        # Single figure legend using the last populated subplot's handles
        handles, labels_leg = axes[0, -1].get_legend_handles_labels()
        fig.legend(handles, labels_leg, loc='center left',
                   bbox_to_anchor=(1.0, 0.5), fontsize=6, ncol=1)

        fig.suptitle('Muscle Moments Comparison', fontsize=12)

        # Sync y-axis limits per row
        for row_idx in range(n_rows):
            y_min = min(axes[row_idx, col_idx].get_ylim()[0] for col_idx in range(n_cols))
            y_max = max(axes[row_idx, col_idx].get_ylim()[1] for col_idx in range(n_cols))
            for col_idx in range(n_cols):
                axes[row_idx, col_idx].set_ylim(y_min, y_max)

        fig.tight_layout()
        save_path = os.path.join(self.results_dir, f'muscle_moments_{self.trialName}.png')
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Muscle moments comparison plot saved: {save_path}")
        self._refresh_results_summary()

    def moment_arms(self):
        '''Plots moment arms for all DOFs in settings.py.
        One figure per DOF. One subplot per muscle (with non-zero moment arm in any model).
        Each line in a subplot represents one model.

        Output: results/moment_arms_<dof>.png
        '''

        dofs = _u.settings.BatchSettings.dof_list

        for dof in dofs:
            # --- collect moment arm data for every model ---
            model_data = {}  # model_name -> DataFrame
            for model_name, trial in self.trials.items():
                if not isinstance(trial, _u.Analyse):
                    continue
                ma_path = os.path.join(trial.path, trial.ma, f'_MuscleAnalysis_MomentArm_{dof}.sto')
                if not os.path.exists(ma_path):
                    print(f"Moment arm file for {dof} not found in {trial.path}. Skipping model {model_name}.")
                    continue
                try:
                    model_data[model_name] = _u.load_any_data_file(ma_path)
                except Exception as e:
                    print(f"Could not load moment arm file for {model_name}, {dof}: {e}")

            if not model_data:
                print(f"No moment arm data found for {dof}. Skipping.")
                continue

            # --- find muscles that have non-zero moment arms in any model ---
            muscles_with_data = set()
            for df in model_data.values():
                muscle_cols = df.columns.drop('time')
                nonzero = _u.openSim.find_non_zero_mom_arm_muscles(df, muscle_cols)
                muscles_with_data.update(nonzero)
            muscles_with_data = sorted(muscles_with_data)

            if not muscles_with_data:
                print(f"No muscles with non-zero moment arms for {dof}. Skipping.")
                continue

            # --- create subplots: one per muscle ---
            n_muscles = len(muscles_with_data)
            n_cols = 4
            n_rows = -(-n_muscles // n_cols)  # ceiling division
            fig, axes = plt.subplots(nrows=n_rows, ncols=n_cols,
                                     figsize=(3 * n_cols, 2.5 * n_rows), sharex=True)
            axes_flat = axes.flatten()

            for i, muscle in enumerate(muscles_with_data):
                ax = axes_flat[i]
                for model_name, df in model_data.items():
                    if muscle in df.columns:
                        ax.plot(df['time'], df[muscle],
                                label=model_name,
                                color=self.colors.get(model_name),
                                linestyle=self.lineStyles.get(model_name, '-'))
                ax.set_title(muscle, fontsize=7)
                ax.axhline(0, color='k', linewidth=0.5, linestyle=':')
                if i % n_cols == 0:
                    ax.set_ylabel('Moment Arm (m)', fontsize=7)
                if i >= n_cols * (n_rows - 1):
                    ax.set_xlabel('Time (s)', fontsize=7)

            # hide unused axes
            for j in range(n_muscles, len(axes_flat)):
                axes_flat[j].set_visible(False)

            # single legend
            handles, labels_leg = axes_flat[0].get_legend_handles_labels()
            fig.legend(handles, labels_leg, loc='lower right', fontsize=7, ncol=2)

            fig.suptitle(f'Moment Arms — {dof}', fontsize=10)
            fig.tight_layout()

            save_path = os.path.join(self.results_dir, f'moment_arms_{dof}.png')
            fig.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f"Moment arms plot saved: {save_path}")
                
                    
          
        # Summary plot with all dofs and models in one figure
        n_cols = 6 
        n_rows = len(dofs) // n_cols + (len(dofs) % n_cols > 0)
        fig, axes = plt.subplots(nrows=n_rows, ncols=n_cols, figsize=(3 * n_cols, 2.5 * n_rows), sharex=True)
        axes_flat = axes.flatten()
        for i, dof in enumerate(dofs):
            # plot spider plot of moment arms for this dof across all models
            ax = axes_flat[i]
            ax.set_title(dof, fontsize=8)
            ax.set_visible(True)

        # hide unused axes
        for j in range(len(dofs), len(axes_flat)):
            axes_flat[j].set_visible(False)

        fig.suptitle('Moment Arms Summary — All DOFs', fontsize=10)
        fig.tight_layout()
        
        save_path = os.path.join(self.results_dir, 'moment_arms_summary.png')
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Moment arms summary plot saved: {save_path}")
        self._refresh_results_summary()

    def summary_errors(self):
        '''Plots summary of errors between models for each DOF'''

        dofs = _u.settings.BatchSettings.dof_list
        n_cols = len(dofs) + 1 # Add an extra column for the mean box plot across DOFs
        n_rows = 5 # IK errors, RMSE and r2 for both Moments and EMG 
        fig, ax = plt.subplots(nrows=n_rows, ncols=n_cols, figsize=(3*n_cols, 3*n_rows), sharex='col')

        # Create summary dataframe to hold error metrics for each model and DOF
        summary_df = pd.DataFrame(columns=['Model', 'DOF', 'Marker_Errors_RMSE_mm', 'Moment_RMSE_percent', 'Moment_R2', 'EMG_RMSE_percent', 'EMG_R2'])

        for model_name, trial in self.trials.items():
            if not isinstance(trial, _u.Analyse):
                print(f"Trial for model {model_name} is not an instance of Analyse. Skipping error summary for this model.")
                continue

            marker_errors = trial.calculate_mean_marker_error()
            moment_errors = trial.calculate_moment_errors()


    def write_results_markdown_summary(self, summary_name: str = 'summary.md') -> str:
        """Create a markdown summary that embeds moment-arm figures and key outputs."""

        def _pretty_coord_name(stem: str) -> str:
            name = stem.replace('moment_arms_', '')
            if name.endswith('_r'):
                name = name[:-2] + ' right'
            elif name.endswith('_l'):
                name = name[:-2] + ' left'
            name = name.replace('_', ' ')
            return name.strip().title()

        def _add_image_block(markdown_lines: list, image_name: str, alt_prefix: str = 'Figure'):
            stem = os.path.splitext(image_name)[0]
            title = _pretty_coord_name(stem)
            markdown_lines.append(f'## {title}')
            markdown_lines.append(f'![{alt_prefix} {title}]({image_name})')
            markdown_lines.append('')

        results_dir = self.results_dir
        os.makedirs(results_dir, exist_ok=True)

        summary_path = os.path.join(results_dir, summary_name)
        file_names = [
            name for name in os.listdir(results_dir)
            if os.path.isfile(os.path.join(results_dir, name)) and name != summary_name
        ]

        png_files = sorted([f for f in file_names if f.lower().endswith('.png')])
        csv_files = sorted([f for f in file_names if f.lower().endswith('.csv')])
        html_files = sorted([f for f in file_names if f.lower().endswith('.html')])

        moment_arm_files = [
            f for f in png_files
            if f.lower().startswith('moment_arms_') and f.lower() != 'moment_arms_summary.png'
        ]

        lines = [
            '# GPK Validation Summary',
            '',
            f'Updated: {time.strftime("%Y-%m-%d %H:%M:%S")}',
            '',
            '## Overview',
            f'- Total files: {len(file_names)}',
            f'- Moment arm figures: {len(moment_arm_files)}',
            f'- Other figures: {len(png_files) - len(moment_arm_files)}',
            f'- CSV files: {len(csv_files)}',
            f'- HTML files: {len(html_files)}',
            '',
            '# Moment arms',
            '',
        ]

        if moment_arm_files:
            for image_name in moment_arm_files:
                _add_image_block(lines, image_name, alt_prefix='Moment arms')
        else:
            lines.append('No moment arm figures found.')
            lines.append('')

        moment_arm_summary = 'moment_arms_summary.png'
        if moment_arm_summary in png_files:
            lines.append('## Moment Arms Summary')
            lines.append(f'![Moment arms summary]({moment_arm_summary})')
            lines.append('')

        other_png_files = [
            f for f in png_files
            if f not in moment_arm_files and f.lower() != 'moment_arms_summary.png'
        ]
        lines.append('# Other figures')
        lines.append('')
        if other_png_files:
            for image_name in other_png_files:
                _add_image_block(lines, image_name, alt_prefix='Figure')
        else:
            lines.append('No additional figure files found.')
            lines.append('')

        lines.append('# CSV outputs')
        lines.append('')
        if csv_files:
            for csv_name in csv_files:
                csv_path = os.path.join(results_dir, csv_name)
                lines.append(f'## {csv_name}')
                try:
                    df = pd.read_csv(csv_path)
                    lines.append(f'- Rows: {len(df)}')
                    lines.append(f'- Columns: {len(df.columns)}')
                    cols_preview = ', '.join(df.columns[:8])
                    if len(df.columns) > 8:
                        cols_preview += ', ...'
                    lines.append(f'- First columns: {cols_preview}')
                except Exception as exc:
                    lines.append(f'- Could not read CSV: {exc}')
                lines.append('')
        else:
            lines.append('No CSV files found.')
            lines.append('')

        if html_files:
            lines.append('# HTML outputs')
            lines.append('')
            for html_name in html_files:
                lines.append(f'- [{html_name}]({html_name})')
            lines.append('')

        with open(summary_path, 'w', encoding='utf-8') as file:
            file.write('\n'.join(lines).rstrip() + '\n')

        self._log(f'Summary markdown updated: {summary_path}', terminal=True)
        return summary_path
