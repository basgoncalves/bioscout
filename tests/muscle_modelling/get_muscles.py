import os
import json
import time
import pandas as pd
import numpy as np
import opensim as osim
import matplotlib.pyplot as plt
import msk_modelling_python as msk
import matplotlib.pyplot as plt 
import xml.etree.ElementTree as ET


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
START_TIME = time.time()
################
def get_muscle_groups(model_path, output_csv=''):
    
    
    model = osim.Model(model_path)
    model.initSystem()
    breakpoint()
    if not output_csv:
        output_csv = os.path.join(MODULE_DIR, 'muscle_groups.csv')

def get_muscles_by_group_osim(xml_path, group_names='all'): 
        members_dict = {}

        try:
            with open(xml_path, 'r', encoding='utf-8') as file:
                tree = ET.parse(xml_path)
                root = tree.getroot()
        except Exception as e:
            print('Error parsing xml file: {}'.format(e))
            return members_dict
        
        if group_names == 'all':
            # Find all ObjectGroup names
            group_names = [group.attrib['name'] for group in root.findall(".//ObjectGroup")]


        members_dict['all_selected'] = []
        for group_name in group_names:
            members = []
            for group in root.findall(".//ObjectGroup[@name='{}']".format(group_name)):
                members_str = group.find('members').text
                members.extend(members_str.split())
            
            members_dict[group_name] = members
            members_dict['all_selected'] = members_dict['all_selected'] + members 

        return members_dict

def get_muscle_per_coordinate(model_path, coordinates = 'all'):
        '''
        This function returns the muscles that are actuating the given coordinates. 
        The function uses the OpenSim API to get the coordinates and the muscles in the model.
        The function returns a dictionary with the coordinates as keys and the muscles as values.
        '''
        # Load the OpenSim model
        model = osim.Model(model_path)
        state = model.initSystem()

        # Get all coordinates in the model
        coordinate_set = model.getCoordinateSet()
          
        if coordinates == 'all':
            coordinates = []
            for i in range(coordinate_set.getSize()):
                coordinates.append(coordinate_set.get(i).getName())
          
        # Get all muscles in the model
        muscle_set = model.getMuscles()
        
        # Create a dictionary to store muscles for each coordinate
        muscles_per_coordinate = {}

        # Loop through each coordinate and find its actuating muscles based on non-zero moment arms
        for i in range(muscle_set.getSize()):
            for coord_name in coordinates:
            
                solver = osim.MomentArmSolver(model)
                muscle = muscle_set.get(i)
                geometry_path = muscle.getGeometryPath()
                coord = coordinate_set.get(coord_name)
                angle = coord.getValue(state)
                coord.setValue(state, angle)
                
                # Compute the moment arm for the muscle at the current coordinate angle
                moment_arm = solver.solve(state,coord, geometry_path)
                
                # Compute the moment arm for the muscle at the maximum coordinate angle
                coord.setValue(state, coord.getRangeMax())
                moment_arm_max = solver.solve(state,coord, geometry_path)
                
                # Compute the moment arm for the muscle at the minimum coordinate angle
                coord.setValue(state, coord.getRangeMin())
                moment_arm_min = solver.solve(state,coord, geometry_path)
                            
                if np.mean([moment_arm, moment_arm_max, moment_arm_min]).round(3) != 0:
                    muscles_per_coordinate[coord_name] = muscle.getName()

            
        return muscles_per_coordinate

def muscle_model_strain():
    # ---------------------------------------------------------------------------
    # Create a muscle model and configure it.
    # ---------------------------------------------------------------------------

    # Define a new muscle model
    muscle_model = osim.Model()
    muscle_model.setUseVisualizer(False)  # Disable visualization

    # Create a body to attach the muscle
    body = osim.Body("body", 1.0, osim.Vec3(0), osim.Inertia(0))
    muscle_model.addBody(body)

    # Create a ground-to-body joint
    joint = osim.PinJoint("joint",
                        muscle_model.getGround(),
                        osim.Vec3(0),
                        osim.Vec3(0),
                        body,
                        osim.Vec3(0),
                        osim.Vec3(0))
    muscle_model.addJoint(joint)

    # Define the muscle
    muscle = osim.Millard2012EquilibriumMuscle("muscle",
                                            200.0,  # Max isometric force
                                            0.6,    # Optimal fiber length
                                            0.55,   # Tendon slack length
                                            0.0)    # Pennation angle
    muscle.addNewPathPoint("origin", muscle_model.getGround(), osim.Vec3(0, 1, 0))
    muscle.addNewPathPoint("insertion", body, osim.Vec3(0, -0.5, 0))
    muscle_model.addForce(muscle)

    # Add a controller to activate the muscle
    controller = osim.PrescribedController()
    controller.addActuator(muscle)
    step_function = osim.StepFunction(0.1, 0.2, 0.3, 0.5)  # Adjust timing and values as needed
    controller.prescribeControlForActuator("muscle", step_function)
    muscle_model.addController(controller)
    
    # ---------------------------------------------------------------------------
    # Configure the simulation.
    # ---------------------------------------------------------------------------

    state = muscle_model.initSystem()
    
    # Simulate with incremental strain increase
    strain = 9
    time_step = 0.1
    total_time = 10.0
    current_time = 0.0
    initial_length = muscle.getFiberLength(state)
    strain_increment = strain / (total_time / time_step)
    breakpoint()

    # Dataframe to store simulation results
    results = pd.DataFrame(columns=["Time", "Force", "Length", "Activation", "Strain"])

    while current_time <= total_time:
        # Incrementally increase strain
        current_strain = (current_time / total_time) * strain
        perturbed_length = initial_length * (1 + current_strain)
        muscle.setFiberLength(state, perturbed_length)
        muscle_model.equilibrateMuscles(state)

        # Record data
        fiber_force = muscle.getFiberForce(state)
        fiber_length = muscle.getFiberLength(state)
        activation = muscle.getActivation(state)
        results.loc[len(results)] = {
            "Time": current_time,
            "Force": fiber_force,
            "Length": fiber_length,
            "Activation": activation,
            "Strain": current_strain
        }

        # Update time
        current_time += time_step

    # ---------------------------------------------------------------------------
    # Plot and save the results.
    # ---------------------------------------------------------------------------
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    
    # Text heading with simulation parameters
    fig.suptitle(f"Muscle Model Simulation\nStrain: {strain}%, Time Step: {time_step}s, Total Time: {total_time}s", fontsize=16)
    fig.text(0.5, 0.95, "Muscle Model Simulation Results", ha='center', fontsize=14)

    # Plot Force
    axs[0, 0].plot(results["Time"], results["Force"], label="Force", color="blue")
    axs[0, 0].set_title("Force vs Time")
    axs[0, 0].set_xlabel("Time (s)")
    axs[0, 0].set_ylabel("Force")
    axs[0, 0].grid()
    axs[0, 0].legend()

    # Plot Length
    axs[0, 1].plot(results["Time"], results["Length"], label="Length", color="green")
    axs[0, 1].set_title("Length vs Time")
    axs[0, 1].set_xlabel("Time (s)")
    axs[0, 1].set_ylabel("Length")
    axs[0, 1].grid()
    axs[0, 1].legend()

    # Plot Activation
    axs[1, 0].plot(results["Time"], results["Activation"], label="Activation", color="red")
    axs[1, 0].set_title("Activation vs Time")
    axs[1, 0].set_xlabel("Time (s)")
    axs[1, 0].set_ylabel("Activation")
    axs[1, 0].grid()
    axs[1, 0].legend()

    # Plot Strain
    axs[1, 1].plot(results["Time"], results["Strain"], label="Strain", color="purple")
    axs[1, 1].set_title("Strain vs Time")
    axs[1, 1].set_xlabel("Time (s)")
    axs[1, 1].set_ylabel("Strain")
    axs[1, 1].grid()
    axs[1, 1].legend()

    # Adjust layout and save the figure
    plt.tight_layout()
    plt.savefig("muscle_simulation_subplots.png")
    plt.show()


if __name__ == "__main__":
    # Define the model path and muscle forces file
    model_path = os.path.join(MODULE_DIR, 'osim_model.osim')
    
    # Get muscle groups and save to CSV
    if False:
        get_muscle_groups(model_path)
    
    # Get muscle groups and save to CSV
    if False:    
        members_dict = get_muscles_by_group_osim(model_path)
        print(members_dict)
    
    if False:    
        muscles_coord = get_muscle_per_coordinate(model_path)
    
    # muscle model strain
    if True:
        muscle_model_strain()
    
    # Print the elapsed time
    print(f"Elapsed time: {time.time() - START_TIME:.2f} seconds")


#%% END