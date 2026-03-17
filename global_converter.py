import csv
import os
import subprocess
import argparse
from rdflib import Graph, URIRef

# Execution:
# python3 global_converter.py 
#  --projects_dir Projects-CSV \
#  --projects_csv projects-common.csv \
#  --output_dir Projects-TTL \
#  --index_file index.ttl

# Argument parser setup
parser = argparse.ArgumentParser(description='Convert project CSV data into TTL format.')
# Input:
parser.add_argument('--projects_dir', type=str, required=True,
                    help='Directory containing CSV files per project with the results of the collected data.')
parser.add_argument('--projects_csv', type=str, required=True,
                    help='CSV file with information about each project.')
# Output:
parser.add_argument('--output_dir', type=str, required=True,
                    help='Directory to store generated TTL files.')
parser.add_argument('--index_file', type=str, required=True,
                    help='TTL file that serves as the index of all projects.')

args = parser.parse_args()

# Assign arguments to variables
projects_dir = args.projects_dir
projects_csv = args.projects_csv
output_dir = args.output_dir
index_file = args.index_file

os.makedirs(output_dir, exist_ok=True)

def build_project_uri(name, version=None, commit=None):
    if version:
        project_uri = URIRef(f"pm:project#{name}_{version}")
    elif commit:
        reduced_commit = commit[:7] if len(commit) >= 7 else commit
        project_uri = URIRef(f"pm:project#{name}_{reduced_commit}")
    else:
        project_uri = URIRef(f"pm:project#{name}")

    return project_uri
            

def process_projects(projects_csv):
    # Load project index data
    graph = Graph()
    graph.parse(index_file, format="turtle")

    # Read the existing projects from the CSV file
    with open(projects_csv, mode='r', newline='') as file:
        reader = csv.DictReader(file)

        # Iterate over each existing project in the CSV
        for row in reader:
            # Extract the data of each project 
            project_name = row["PROJECT_NAME"]
            project_url = row["PROJECT_URL"]
            project_version = row["PROJECT_VERSION"]
            project_commit = row["PROJECT_COMMIT"]
            language = row["LANGUAGE"]
            testsuite_url = row["TESTSUITE_URL"]
            testsuite_name = row["TESTSUITE_NAME"]
            target_tests = row["TARGET_TESTS"]
            excluded_tests = row["EXCLUDED_TESTS"]
            added_tests = row["ADDED_TESTS"]
            pair_type = row["PAIR_TYPE"]		#TS (mutant-test suite), TC (mutant-test case)
            channel = row["CHANNEL"]			#AL, NL, BOTH
            
            # Generate the URI to skip this project if it is already included in the TTL file,
            # based on the availability of version or commit.
            project_uri = build_project_uri(project_name, project_version, project_commit)
            if (project_uri, None, None) in graph:
                print(f"The project <{project_uri}> already exists in the index file.")
                continue
            
            # Generate the CSV and TTL filename for the project, depending on version or commit availability
            # Also, the command is assembled here
            command = f"python3 project_converter.py {pair_type} {channel} {language} {project_name} {project_url} "
            if project_version:
                project_csv = f"{projects_dir}/{project_name}_{project_version}_results.csv"
                project_ttl = f"{output_dir}/output_{project_name}_{project_version}.ttl"
                command += f"{project_version} None "
            elif project_commit:
                project_csv = f"{projects_dir}/{project_name}_{project_commit}_results.csv"
                project_ttl = f"{output_dir}/output_{project_name}_{project_commit}.ttl"
                command += f"None {project_commit} "
            else:
                project_csv = f"{projects_dir}/{project_name}_results.csv"
                project_ttl = f"{output_dir}/output_{project_name}.ttl"
                command += f"None None "
            
            command += f"{project_csv} {project_ttl} {index_file} {testsuite_url} "
            
            # Add additional command options related to tests
            for tests in [testsuite_name, target_tests, excluded_tests, added_tests]:
                command += f"{tests if tests else 'None'} "
            
            # Check if the mutant file exists
            if not os.path.isfile(project_csv):
                print(f"CSV file not found for project '{project_csv}'.")
                continue
            
            # Execute the `project_converter.py` script with the command arguments
            try:
                subprocess.run(command, shell=True, check=True)
                print(f"Turtle file generated for '{project_name}': {project_ttl}")
            except subprocess.CalledProcessError as e:
                print(f"Error generating file for '{project_name}': {e}")

# Run the project processing function
process_projects(projects_csv)
