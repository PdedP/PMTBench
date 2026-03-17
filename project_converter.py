import csv
import sys
import os
from pathlib import Path
import json
import ast

# Execution: 
# python3 project_converter.py
#     <pair_type> <channel> <language> 
#     <PROJECT_NAME> <PROJECT_URL> <PROJECT_VERSION> <PROJECT_COMMIT> 
#     <project_csv> <project_ttl> <index_path>
#     <TESTSUITE_URL> <TESTSUITE_NAME> <target_tests> <excluded_tests> <added_tests>


### -------------------- CONFIGURATION DATA -------------------------- ###

# Define the heading
HEADING = "@prefix pm: <https://b2share.eudat.eu/records/90aa1d6fa6c74a73adc4e0ba64771367/> .\n@prefix schema: <http://schema.org/> ."

# Define the citation
citation_id = "<pm:paper#zhao2024spotting>"
#citation_id = "<pm:paper#pmtbenchAL>"
citation_data = ""
citation_data = [f"""
{citation_id} a schema:CreativeWork ;
    schema:author <mb:person#Yifan.Zhao>, 
        <mb:person#Yizhou.Chen>,
        <mb:person#Zeyu.Sun>,
        <mb:person#Qingyuan.Liang>,
        <mb:person#Guoqing.Wang>,
        <mb:person#Dan.Hao> ;
    schema:name "Spotting Code Mutation for Predictive Mutation Testing" ;
    schema:sameAs "https://doi.org/10.1145/3691620.3695491" .
""".strip()]

# Define the dictionaries of metrics
static_metrics = {
    'DIT': 'Depth of Inheritance Tree',     # class
    'NOCh': 'Number of Children',           # class 
    'VG': 'McCabe Cyclomatic Complexity',   # method
    'TLOC': 'Total Lines of Code',          # method
    'NBD': 'Nested Block Depth',            # method
    'Ce': 'Efferent Coupling',              # package
    'Ca': 'Afferent Coupling',              # package
    'I': 'Instability'                      # package
}

dynamic_metrics = {
    'NumTestCovered': 'Number of Test Cases Covered',
    'NumExecuteCovered': 'Number of Execute Covered',
    'NumMutantAssertion': 'Number of Mutant Assertions',
    'NumClassAssertion': 'Number of Class Assertions'
}

nl_metrics = {
    'SrcLines': 'Lines of the mutated method',
    'MutSrcLineNo': 'Number of mutated line in src_lines',
    'Before': 'Modified code in the original file before mutation',
    'After': 'Modified code in the mutant',
    'BeforePMT': 'Processed content of before',
    'AfterPMT': 'Processed content of after',
    'Body': 'Body of the mutated line'
}

# Define the data of the tools used
#MUTATION_TOOL = "<pm:tool#PIT_1.15.8>"
MUTATION_TOOL = "<pm:tool#Major_1.3.4>"
mutation_tool_details = MUTATION_TOOL.strip("<>").split("#")[1]
mutation_tool_name, mutation_tool_version = mutation_tool_details.split("_")

#COVERAGE_TOOL = "<pm:tool#OpenClover_4.5.2>"
COVERAGE_TOOL = "<pm:tool#Cobertura_2.0.3>"
coverage_tool_details = COVERAGE_TOOL.strip("<>").split("#")[1]
coverage_tool_name, coverage_tool_version = coverage_tool_details.split("_")

ANALYSIS_TOOL = "<pm:tool#JaSoMe_v0.6.8-alpha>"
analysis_tool_details = ANALYSIS_TOOL.strip("<>").split("#")[1]
analysis_tool_name, analysis_tool_version = analysis_tool_details.split("_")

### -------------------- FUNCTIONS -------------------------- ###

# Function to generate the execution block for test case pairs
def build_execution_block_tc(test_paths, test_killing_paths, test_passing_paths, mutant_id, testsuite_id, row, channel, test_path_to_id):
    
    killing_tests = set(test_killing_paths)
    passing_tests = set(test_passing_paths)

    # Step 1: Reconstruct test_paths by adding missing ones from killing/passing
    missing_tests = (killing_tests | passing_tests) - set(test_paths)
    if missing_tests:
        print(f"[INFO] Adding missing tests to test_paths: {missing_tests}")
        test_paths = list(test_paths) + list(missing_tests)

    executed_tests = []
    killed_tests = []
    survived_tests = []

    for test_path in test_paths:
        test_id = test_path_to_id.get(test_path)
        if not test_id:
            print(f"No test_id for: {test_path}")
            continue

        if test_path in killing_tests:
            executed_tests.append(f"<pm:test#{test_id}>")
            killed_tests.append(f"<pm:test#{test_id}>")
        elif test_path in passing_tests:
            executed_tests.append(f"<pm:test#{test_id}>")
            survived_tests.append(f"<pm:test#{test_id}>")
        else:
            print(f"Skipping test with unknown result: {test_path}")

    label = row['Status']

    # Consistency checks
    # 1) If no tests for this mutant, then the conversion is not valid
    if not killed_tests and not survived_tests:
        print(f"[ERROR] No valid test results for mutant {mutant_id}.")
        return []

    # 2) If the killing tests list is empty and the label is KILLED, we change the label to keep consistency
    if label == "KILLED" and not killed_tests:
        print(f"Label KILLED but no killed tests found for mutant {mutant_id}. Changing label to SURVIVED.")
        label = "SURVIVED"

    # Generate the execution identifier
    execution_id = f"{mutant_id}_{testsuite_id}"

    # Define the execution block
    execution_data = f""" 
<pm:execution#{execution_id}> a pm:Execution ;
    pm:label "{label}" ;
    pm:analyzedByTool {COVERAGE_TOOL} ;
    pm:executedOnMutant <pm:mutant#{mutant_id}> ;
    pm:executedByTestSuite <pm:testsuite#{testsuite_id}> ;
    pm:executedByTestCases ({' '.join(executed_tests)}) ;
    pm:killedByTestCases ({' '.join(killed_tests)}) ;
    pm:survivedToTestCases ({' '.join(survived_tests)}) ;
""".strip()

    if channel in ("AL", "BOTH"):
        # Dynamically add the metrics defined in the dictionary
        for metric in dynamic_metrics:
            if metric in row: # Check if the metric is present in `row`
                # The format should be: [4, 1, ... 3]
                values = row[metric].strip("[]").split(",")
                rdf_list = "({})".format(" ".join(v.strip() for v in values if v.strip()))
                execution_data += f'\n    pm:{metric} {rdf_list} ;'
    execution_data = execution_data[:-1] + "."
    execution_data.strip()
    
    return execution_data


# Function to generate the execution block for test suite granularity
def build_execution_block_ts(row, mutant_id, testsuite_id, dynamic_metrics):

    # Generate the execution identifier
    execution_id = f"{mutant_id}_{testsuite_id}"
    
    # Define the execution block
    execution_data = f"""
<pm:execution#{execution_id}> a pm:Execution ;
    pm:label "{row['Label']}" ;
    pm:analyzedByTool {COVERAGE_TOOL} ;
    pm:executedOnMutant <pm:mutant#{mutant_id}> ;
    pm:executedByTestSuite <pm:testsuite#{testsuite_id}> ;
""".strip()
    
    # Dynamically add the metrics defined in the dictionary
    for metric in dynamic_metrics.keys():
        if metric in row:  # Check if the metric is present in `row`
            execution_data += f'\n    pm:{metric} {row[metric]} ;'
    execution_data = execution_data[:-1] + "."
    execution_data.strip()

    return execution_data
 
    
# Prepare source lines to avoid formatting issues    
def prepare_src_lines(raw_string):
    try:
        lines = ast.literal_eval(raw_string)
        if not isinstance(lines, list):
            raise ValueError(f"Expected a list for SrcLines")

        turtle_items = []

        for line in lines:
            if '"' in line:
                escaped = line.replace('"""', '\\"""')  
                turtle_items.append(f'"""{escaped}"""')
            else:
                turtle_items.append(f'"{line}"')
        return f"( {' '.join(turtle_items)} )"
    except Exception as e:
        print(f"Error processing SrcLines: {e}")
        return '()'
        

# Function to generate the NL block
def build_natural_language_rdf(row, mutant_id):
   
    # Generate the natural language identifier
    nl_id = mutant_id

    # Define the natural language block
    nl_data = f"""
<pm:naturalLanguage#{nl_id}> a pm:NaturalLanguage ;
    pm:refersToMutant <pm:mutant#{mutant_id}> ;
""".strip()

    # Dynamically add the metrics defined in the dictionary
    for metric in nl_metrics.keys():
        if metric in row:  # Check if the metric is present in `row`
            value = row[metric]
            if metric == "SrcLines":
                turtle_list = prepare_src_lines(row['SrcLines'])
                nl_data += f'\n    pm:SrcLines {turtle_list} ;'
            else:
                escaped = value.replace('"', '\\"')
                nl_data += f'\n    pm:{metric} "{escaped}" ;'

    nl_data = nl_data[:-1] + "."
    nl_data.strip()

    return nl_data


# Function to generate the static block
def build_static_rdf(row, mutant_id):
    
    # Generate the static identifier
    static_id = mutant_id

    # Create the static block
    static_data = f"""\
<pm:staticAnalysis#{static_id}> a pm:StaticAnalysis ;
    pm:analyzedMutant <pm:mutant#{mutant_id}> ;
    pm:analyzedByTool {ANALYSIS_TOOL} ;
    pm:typeReturn "{row['TypeReturn']}" ;
""".strip()

    # Dynamically add the static metrics
    for key, description in static_metrics.items():
        if key in row:  # Check if the metric is present in `row`
            static_data += f'\n    pm:{key} {row[key]} ;'
    static_data = static_data[:-1] + "."
    static_data.strip()

    return static_data
 
 
# Function to generate the mutant block
def build_mutant_rdf(row, file_id):

    # Generate the mutant identifier
    line = row['Line']
    operator = row['Operator']
    count = row['Count']
    mutant_id = f"{file_id}_{line}_{operator}_{count}_{mutation_tool_details}"

    # Create the mutant block
    mutant_data = f"""
<pm:mutant#{mutant_id}> a pm:Mutant ;
    pm:generatedByTool {MUTATION_TOOL} ;
    pm:method "{row['Method']}" ;
    pm:line {line} ;
    pm:operator "{operator}" ;
    pm:count {count} ;
    pm:originalFile <pm:file#{file_id}> .
""".strip()

    # Note: the following property can be added to pm:Mutant if the information is available
    # pm:equivalence "false"^^schema:boolean ;

    return mutant_id, mutant_data


# Function to generate the file block
def build_file_rdf(row, project_id, language, file_ids):

    # Get the package and file name
    class_path = row['Class']
    package, file_name = class_path.rsplit('.', 1)
    
    # Generate the file identifier
    file_id = f"{project_id}_{class_path}.{language}"

    # Create the file block only if it has not been added before
    if file_id not in file_ids:
        file_ids[file_id] = f"""
<pm:file#{file_id}> a pm:File ;
    schema:name "{file_name}" ;
    schema:programmingLanguage "{language}" ;
    pm:extension "java" ;
    pm:fileName "{file_name}.{language}" ;
    pm:package "{package}" ;
    pm:partOfProject <pm:project#{project_id}> .
""".strip()

    return file_id

    
# Function to generate mutant blocks, collected data blocks (static, dynamic and NL) and files block     
def build_mutation_rdf(config, project_id, testsuite_id, test_path_to_id):
    rdf_data = []
    
    project_csv = config["project_csv"]
    language = config["language"]
    channel = config["channel"]
    pair_type = config["pair_type"]

    # Unique added elements
    file_ids = {}
    mutant_ids = set()

    # Read the CSV file of the project
    with open(project_csv, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            
            # Generate the file block
            file_id = build_file_rdf(row, project_id, language, file_ids)
            
            # Generate the mutant block
            mutant_id, mutant_data = build_mutant_rdf(row, file_id)
            
            # EXECUTION DATA: Always, but with different information:
            # - AL channel and pair_type == ts : complete execution and executedByTestSuite
            # - AL channel and pair_type == tc : complete execution and executedByTestCase 
            # - NL channel and pair_type == tc : only label and executedByTestCase
            # - BOTH channel and pair_type == tc: complete execution and executedByTestCase
            execution_data = []
            if pair_type == "ts":
                execution_data = build_execution_block_ts(row, mutant_id, testsuite_id, dynamic_metrics)
            else:         # pair_type == tc
                test_paths = ast.literal_eval(row["Tests"])
                test_kill_paths = ast.literal_eval(row["KillingTests"])
                test_pass_paths = ast.literal_eval(row["PassingTests"])

                execution_data = build_execution_block_tc(test_paths, test_kill_paths, test_pass_paths, 
                                     mutant_id, testsuite_id, row, channel, test_path_to_id)            
            
            # If the execution block was not generated, then we skip the mutant
            if not execution_data:
                print(f"Skipping mutant {mutant_id} due to inconsistent execution data.")
                continue 
            
            # Create the mutant block only if it has not been added before
            if mutant_id not in mutant_ids:
                rdf_data.append(mutant_data)
                mutant_ids.add(mutant_id)
            else:
                print(f"Duplicate mutant id: {mutant_id}")
            
            # Generate the static block, when the channel is AL or BOTH 
            if channel in ("AL", "BOTH"):
                static_block = build_static_rdf(row, mutant_id)
                rdf_data.append(static_block)

            # Generate the NL block , when the channel is NL or BOTH
            if channel in ("NL", "BOTH"):
                nl_data = build_natural_language_rdf(row, mutant_id)
                rdf_data.append(nl_data)

            # Add the execution block
            rdf_data.append(execution_data)

    # Add unique files
    rdf_data.extend(file_ids.values())

    return rdf_data


# Function to generate test case blocks
def build_testcases_rdf(config, testsuite_id):
    testcases_data = []
    test_path_to_id = {}

    test_map_path = Path(str(config["project_csv"]).replace("_results.csv", "_test_map.csv"))
    if not test_map_path.exists():
        print(f"File {test_map_path} not found.")
        return testcases_data, test_path_to_id

    with open(test_map_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_path = row['TestMethod']
            test_code = row['TestMethodCode']
            try:
                package_test, testfile_name, test_name = test_path.rsplit('.', 2)
            except ValueError:
                print(f"Unexpected format in TestMethod: {test_path}")
                continue

            test_id = f"{testsuite_id}_{test_path}"
            test_path_to_id[test_path] = test_id

            testcases_data.append(f"""
<pm:test#{test_id}> a pm:Test ;
    schema:name "{test_name}" ;
    pm:testMethodName "{package_test}.{testfile_name}.{test_name}" ;
    pm:fileName "{testfile_name}.java" ;
    pm:package "{package_test}" ;
    pm:testMethodCode {json.dumps(test_code)} ;
    pm:partOfTestSuite <pm:testsuite#{testsuite_id}> .
""".strip())

    return testcases_data, test_path_to_id

    
# Function to generate test suite block
def build_testsuite_rdf(config, project_id):
    testsuite_url = config["testsuite_url"]
    testsuite_name = config["testsuite_name"]
    target_tests = config["target_tests"]
    excluded_tests = config["excluded_tests"]
    added_tests = config["added_tests"]
   
    # Generate the test suite id
    testsuite_id = f"{project_id}_{testsuite_name}"

    # Define the test suite block
    test_data = f"""
<pm:testsuite#{testsuite_id}> a pm:TestSuite ;
    schema:name "{testsuite_name}" ;
    schema:codeRepository "{testsuite_url}"^^schema:URL ;
""".strip()

    # Conditionally add the additional properties
    if target_tests:
        test_data += f'\n    pm:targetTests "{target_tests}" ;'
    if excluded_tests:
        test_data += f'\n    pm:excludedTests "{excluded_tests}" ;'
    if added_tests:
        test_data += f'\n    pm:addedTests "{added_tests}" ;'
    
    test_data += f"\n    pm:partOfProject <pm:project#{project_id}> ."    
    test_data = test_data[:-1] + "."
    test_data.strip()
    
    return test_data, testsuite_id    
    
    
# Function to generate the blocks for tools
def build_tools_rdf(config):
    rdf_data = []

    rdf_data.append(f"""
{MUTATION_TOOL} a pm:MutationTool ;
    schema:name "{mutation_tool_name}" ;
    schema:softwareVersion "{mutation_tool_version}" .
    
{COVERAGE_TOOL} a pm:CoverageTool ;
    schema:name "{coverage_tool_name}" ;
    schema:softwareVersion "{coverage_tool_version}" .
""".strip())

    if config["channel"] in ("AL", "BOTH"):
        rdf_data.append(f"""
{ANALYSIS_TOOL} a pm:AnalysisTool ;
    schema:name "{analysis_tool_name}" ;
    schema:softwareVersion "{analysis_tool_version}" .
""".strip())

    return rdf_data
    

# Function to generate the project and citation blocks
def build_project_rdf(config):
   
    # NOTE: project and index data has to be handled separately.
    # This is because the project TTL file always includes the header,
    # while the index does not if other projects already exist
    rdf_data_index = []   # for index.ttl
    rdf_data = [] 	  # for the rest of data
    rdf_project = []      # for the project
    
    project_name = config["project_name"]
    project_url = config["project_url"]
    project_ttl = config["project_ttl"]
    project_version = config["project_version"]
    project_commit = config["project_commit"]
    
    # Define the project block
    if project_version:
        project_id = f"{project_name}_{project_version}"
        rdf_project.append(f"""
<pm:project#{project_id}> a pm:Project ;
    schema:name "{project_name}" ;
    schema:codeRepository "{project_url}"^^schema:URL ;
    schema:citation "{citation_id}" ; 
    schema:version "{project_version}" ;
    pm:ttlFile "{project_ttl}" .
""".strip())
    elif project_commit:
         # Use the first 7 characters of the commit hash (as commonly shown in GitHub)
        reduced_commit = project_commit[:7] if len(project_commit) >= 7 else project_commit
        project_id = f"{project_name}_{reduced_commit}"
        rdf_project.append(f"""
<pm:project#{project_id}> a pm:Project ;
    schema:name "{project_name}" ;
    schema:codeRepository "{project_url}"^^schema:URL ;
    schema:citation "{citation_id}" ; 
    pm:commit "{project_commit}" ;
    pm:ttlFile "{project_ttl}" .
""".strip())
    else:
        project_id = f"{project_name}"
        rdf_project.append(f"""
<pm:project#{project_id}> a pm:Project ;
    schema:name "{project_name}" ;
    schema:codeRepository "{project_url}"^^schema:URL ;
    schema:citation "{citation_id}" ; 
    pm:ttlFile "{project_ttl}" .
""".strip())

    # Create the index.ttl file if it does not exist, or add the new entry if it does
    index_path = config["index_path"]
    if os.path.exists(index_path) and os.stat(index_path).st_size == 0:
        rdf_data_index.append(HEADING)

    with open(index_path, 'a') as index_file:
       rdf_data_index.extend(rdf_project)
       output_index = "\n\n\n".join(rdf_data_index) + "\n\n"
       index_file.write(output_index)

    rdf_data.append(HEADING)
    rdf_data.extend(rdf_project)
    rdf_data.extend(citation_data)
 
    return rdf_data, project_id
     
     
# Function to validate the configuration of channel and pair_type
def validate_config(config):
    if config["channel"] in ("NL", "BOTH") and config["pair_type"] == "ts":
        print("Combination of channel and pair_type not supported")
        sys.exit(1)


# Function to capture the command-line arguments
def parse_arguments(args):
    if len(args) != 16:
        print("Usage: python3 project_converter.py <pair_type> <channel> <language> <PROJECT_NAME> "
              "<PROJECT_URL> <PROJECT_VERSION> <PROJECT_COMMIT> <project_csv> <project_ttl> <index_ttl> "
              "<TESTSUITE_URL> <TESTSUITE_NAME> <target_tests> <excluded_tests> <added_tests>")
        sys.exit(1)

    return {
        "pair_type":        args[1],
        "channel":          args[2],
        "language":         args[3],
        "project_name":     args[4],
        "project_url":      args[5],
        "project_version":  None if args[6] == 'None' else args[6],
        "project_commit":   None if args[7] == 'None' else args[7],
        "project_csv":      args[8],
        "project_ttl":      args[9],
        "index_path":       args[10],
        "testsuite_url":    args[11],
        "testsuite_name":   args[12] if args[12] != 'None' else "testsuite_1",
        "target_tests":     None if args[13] == 'None' else args[13],
        "excluded_tests":   None if args[14] == 'None' else args[14],
        "added_tests":      None if args[15] == 'None' else args[15],
    }


# Main function
if __name__ == "__main__":
    
    # Parse arguments
    config = parse_arguments(sys.argv)
    
    # Validate configuration 
    validate_config(config)
    
    # Write project data
    rdf_data, project_id = build_project_rdf(config)
    
    # Write the tools data
    tools_data = build_tools_rdf(config)
    rdf_data.extend(tools_data)
    
    # Write the test suite data
    test_data, testsuite_id = build_testsuite_rdf(config, project_id)
    rdf_data.append(test_data)
    
    # Write the test cases data
    test_path_to_id = {}
    if config["pair_type"] == "tc":
        testcases_data, test_path_to_id = build_testcases_rdf(config, testsuite_id)
        rdf_data.extend(testcases_data)    
    
    # Write the mutants data, the collected data and the files data
    mutation_blocks = build_mutation_rdf(config, project_id, testsuite_id, test_path_to_id)
    rdf_data.extend(mutation_blocks)

    # Generate the output file with a single blank line between blocks
    output = "\n\n".join(rdf_data)
    with open(config["project_ttl"], 'w') as f:
        f.write(output)
