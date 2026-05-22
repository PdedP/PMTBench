import argparse
import csv
import os
import random
import subprocess
import ast
import sys
import yaml
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from rdflib import Graph, Namespace, URIRef, Literal, RDF
from rdflib.collection import Collection
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix


# Define namespaces
PMTB = Namespace("https://b2share.eudat.eu/records/90aa1d6fa6c74a73adc4e0ba64771367/")
SCHEMA = Namespace("http://schema.org/")


# Dictionary of metrics
static_metrics = {
    "DIT": "Depth of Inheritance Tree",     # class
    "NOCh": "Number of Children",           # class
    "VG": "McCabe Cyclomatic Complexity",   # method
    "TLOC": "Total Lines of Code",          # method
    "NBD": "Nested Block Depth",            # method
    "Ce": "Efferent Coupling",              # package
    "Ca": "Afferent Coupling",              # package
    "I": "Instability"                      # package
}

dynamic_metrics = {
    "NumTestCovered": "Number of Test Cases Covered",
    "NumExecuteCovered": "Number of Execute Covered",
    "NumMutantAssertion": "Number of Mutant Assertions",
    "NumClassAssertion": "Number of Class Assertions"
}

nl_metrics = {
    "SrcLines": "Lines of the mutated method",
    "MutSrcLineNo": "Number of mutated line in src_lines",
    "Before": "Modified code in the original file before mutation",
    "After": "Modified code in the mutant",
    "BeforePMT": "Processed content of before",
    "AfterPMT": "Processed content of after",
    "Body": "Body of the mutated line"
}

tests = {
    "executedByTestCases": "Tests",
    "killedByTestCases": "KillingTests",
    "survivedToTestCases": "PassingTests",
}


def set_global_determinism(seed: int) -> None:
    """
    Set the random seed for all randomness directly controlled by this script.

    Notes:
    - PYTHONHASHSEED affects subprocesses when passed through the environment.
    - Iteration order over RDF graphs and dictionaries is made deterministic
      explicitly by sorting wherever needed.
    """
    if seed is None:
        return

    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)


# Function to save metrics to a CSV file
def save_metrics_csv(metrics_dict, csv_file):
    """
    Save classification metrics (one or two levels) to a CSV file.

    :param metrics_dict: Dictionary with metrics per level
    :param csv_file: Path to save the CSV file
    """
    try:
        with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            for level, data in metrics_dict.items():
                metrics = data["metrics"]
                labels = data["labels"]

                writer.writerow([f"{level} level metrics"])
                writer.writerow(["", "Precision", "Recall", "F1-score", "Support"])
                for label in labels:
                    writer.writerow([
                        label,
                        f"{metrics['precision_per_class'][label]:.4f}",
                        f"{metrics['recall_per_class'][label]:.4f}",
                        f"{metrics['f1_per_class'][label]:.4f}",
                        f"{metrics['support_per_class'][label]}"
                    ])

                writer.writerow([
                    "Macro",
                    f"{metrics['macro_precision']:.4f}",
                    f"{metrics['macro_recall']:.4f}",
                    f"{metrics['macro_f1']:.4f}",
                    "-"
                ])

                writer.writerow([
                    "Weighted",
                    f"{metrics['weighted_precision']:.4f}",
                    f"{metrics['weighted_recall']:.4f}",
                    f"{metrics['weighted_f1']:.4f}",
                    "-"
                ])

                writer.writerow([])
                writer.writerow(["Accuracy", f"{metrics['accuracy']:.4f}"])
                writer.writerow([])

                if "mutation_score_per_project" in metrics:
                    writer.writerow(["Project", "MutationScore_Real", "MutationScore_Predicted", "Error"])
                    for ms in metrics["mutation_score_per_project"]:
                        writer.writerow([
                            ms["project"],
                            f"{ms['real']:.4f}",
                            f"{ms['pred']:.4f}",
                            f"{ms['error']:.4f}"
                        ])
                    writer.writerow(["Average_Error", "", "", f"{metrics['error_average']:.4f}"])
                    writer.writerow([])

        print(f"Metrics successfully saved to {csv_file}")
    except Exception as e:
        print(f"Error while writing metrics to CSV: {e}")


# Function to plot the confusion matrix
def plot_confusion_matrix(true_labels, predicted_labels, labels, output_file):
    """
    Plot a confusion matrix using a seaborn heatmap.

    :param true_labels: List of true labels
    :param predicted_labels: List of predicted labels
    :param labels: List of class labels
    :param output_file: File to save the confusion matrix
    """
    cm = confusion_matrix(true_labels, predicted_labels, labels=labels)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=labels, yticklabels=labels)
    plt.xlabel("Predicted Label")
    plt.ylabel("True Label")
    plt.title("Confusion Matrix")
    plt.tight_layout()
    plt.savefig(output_file)
    print(f"Confusion matrix saved to {output_file}")
    plt.close()


# Function to calculate and print global and per-class metrics
def compute_and_print_metrics(true_labels, predicted_labels, test_case=True, threshold=None):
    """
    Compute and print classification metrics.

    :param true_labels: List of true labels
    :param predicted_labels: List of predicted labels
    :param test_case: True for test-case level, False for test-suite level
    :param threshold: Threshold used for test-suite aggregation, if applicable
    """
    # Per-class metrics
    precision, recall, f1_score, support = precision_recall_fscore_support(
        true_labels, predicted_labels, average=None, zero_division=1
    )

    # Global metrics
    acc = accuracy_score(true_labels, predicted_labels)
    p_macro, r_macro, f1_macro, _ = precision_recall_fscore_support(
        true_labels, predicted_labels, average="macro", zero_division=1
    )
    p_weight, r_weight, f1_weight, _ = precision_recall_fscore_support(
        true_labels, predicted_labels, average="weighted", zero_division=1
    )

    # Print global metrics
    if test_case:
        print("\n=== Test-case level metrics: ===")
    else:
        if threshold is not None:
            print(f"\n=== Test-suite level metrics (threshold={threshold}): ===")
        else:
            print("\n=== Test-suite level metrics ===")

    print(f"Accuracy: {acc:.4f}")
    print(f"Macro Precision: {p_macro:.4f}")
    print(f"Macro Recall:    {r_macro:.4f}")
    print(f"Macro F1-score:  {f1_macro:.4f}")
    print(f"Weighted Precision: {p_weight:.4f}")
    print(f"Weighted Recall:    {r_weight:.4f}")
    print(f"Weighted F1-score:  {f1_weight:.4f}\n")

    # Print per-class metrics
    labels = sorted(set(true_labels + predicted_labels))
    for i, label in enumerate(labels):
        print(f"Class: {label}")
        print(f"  Precision: {precision[i]:.4f}")
        print(f"  Recall:    {recall[i]:.4f}")
        print(f"  F1-score:  {f1_score[i]:.4f}")
        print(f"  Support:   {support[i]}")

    metrics = {
        "accuracy": acc,
        "macro_precision": p_macro,
        "macro_recall": r_macro,
        "macro_f1": f1_macro,
        "weighted_precision": p_weight,
        "weighted_recall": r_weight,
        "weighted_f1": f1_weight,
        "precision_per_class": dict(zip(labels, precision)),
        "recall_per_class": dict(zip(labels, recall)),
        "f1_per_class": dict(zip(labels, f1_score)),
        "support_per_class": dict(zip(labels, support))
    }

    return metrics, labels


# Function to calculate and print mutation score error
def compute_and_print_mutation_score(mutant_level_data):
    """
    Compute and print mutation score error per project and the average error.

    :param mutant_level_data: Dictionary with true and predicted labels grouped by project
    """
    ms_results = []

    for proj in sorted(mutant_level_data):
        values = mutant_level_data[proj]
        true_proj = [t for t, _ in values]
        pred_proj = [p for _, p in values]

        killed_true = sum(1 for t in true_proj if t == "KILLED")
        ms_true = killed_true / len(true_proj) if true_proj else 0

        killed_pred = sum(1 for p in pred_proj if p == "KILLED")
        ms_pred = killed_pred / len(pred_proj) if pred_proj else 0

        ms_error = abs(ms_true - ms_pred)
        ms_results.append((proj, ms_true, ms_pred, ms_error))

    max_proj_len = max(len(proj) for proj, _, _, _ in ms_results)
    header_fmt = f"{{:<{max_proj_len}}}  {{:<12}} {{:<12}} {{:<12}}"
    row_fmt = f"{{:<{max_proj_len}}}  {{:<12.4f}} {{:<12.4f}} {{:<12.4f}}"

    print("\n===== Mutation score error =====")
    print(header_fmt.format("Project", "MS Real", "MS Predicted", "MS Error"))

    for proj, ms_true, ms_pred, ms_error in ms_results:
        print(row_fmt.format(proj, ms_true, ms_pred, ms_error))

    avg_mse = sum(ms_error for _, _, _, ms_error in ms_results) / len(ms_results)
    print(f"\nAverage mutation score error: {avg_mse:.4f}")

    mutation_scores = [
        {"project": proj, "real": ms_true, "pred": ms_pred, "error": ms_error}
        for proj, ms_true, ms_pred, ms_error in ms_results
    ]

    return mutation_scores, avg_mse


# Function to aggregate test-case level predictions into test-suite level predictions
def aggregate_mutant_labels(true_list, pred_list, prob_list, threshold=0.25):
    """
    Aggregate test-case level predictions into test-suite level predictions.
    If probabilities exist, they are used with the given threshold.
    Otherwise, predicted labels ("KILLED"/"SURVIVED") are used directly.

    :param true_list: List of true labels for each test case of the mutant
    :param pred_list: List of predicted labels for each test case of the mutant
    :param prob_list: List of predicted probabilities for each test case of the mutant
    :param threshold: Probability threshold used to decide if a mutant is considered KILLED
    """
    if prob_list:
        # Case: probability column exists and is not empty
        true_label = "KILLED" if "KILLED" in true_list else "SURVIVED"
        pred_label = "KILLED" if any(p >= threshold for p in prob_list) else "SURVIVED"
    else:
        # Case: no probability column, fall back to label aggregation
        true_label = "KILLED" if "KILLED" in true_list else "SURVIVED"
        pred_label = "KILLED" if "KILLED" in pred_list else "SURVIVED"

    return true_label, pred_label


# Function to evaluate the model's performance based on the output file generated by the ML script
def evaluate_model(output_file, metrics_csv_file=None, threshold=None):
    """
    Compute metrics by comparing predicted labels to true labels.
    Display per-class, global, and weighted metrics.
    Optionally save results to CSV.

    :param output_file: Path to the output file generated by the ML script
    :param metrics_csv_file: Optional path to save metrics
    :param threshold: Optional probability threshold
    """
    true_labels, predicted_labels, projects = [], [], []
    mutant_level_data = defaultdict(list)
    case_level = False  # Flag to detect test-case level predictions

    try:
        with open(output_file, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                project = row["Project"]
                true_val = row["True Label"]
                pred_val = row["Predicted Label"]

                # Detect test-case level lists
                if true_val.startswith("[") and pred_val.startswith("["):
                    case_level = True
                    true_list = ast.literal_eval(true_val)
                    pred_list = ast.literal_eval(pred_val)

                    # Expand lists for global metrics
                    true_labels.extend(true_list)
                    predicted_labels.extend(pred_list)
                    projects.extend([project] * len(true_list))

                    # Aggregate one label per mutant
                    prob_list = []
                    if "Killing Probability" in row and row["Killing Probability"]:
                        prob_list = ast.literal_eval(row["Killing Probability"])

                    if threshold is not None:
                        true_label, pred_label = aggregate_mutant_labels(
                            true_list, pred_list, prob_list, threshold
                        )
                    else:
                        true_label, pred_label = aggregate_mutant_labels(
                            true_list, pred_list, prob_list
                        )
                    mutant_level_data[project].append((true_label, pred_label))

                # Test-suite level prediction
                else:
                    true_labels.append(true_val)
                    predicted_labels.append(pred_val)
                    projects.append(project)
                    mutant_level_data[project].append((true_val, pred_val))

        if not true_labels:
            print("Error: The output file is empty or does not contain labels.")
            sys.exit(1)

        # Global and per-class metrics
        results_to_save = {}

        # Case 1: test-case predictions -> compute metrics at test-case and test-suite level
        if case_level:
            metrics_case, labels = compute_and_print_metrics(true_labels, predicted_labels, True)
            results_to_save["Test-case"] = {"metrics": metrics_case, "labels": labels}

            # Aggregate test-suite level labels from mutant_level_data
            true_suite = [t for values in mutant_level_data.values() for t, _ in values]
            pred_suite = [p for values in mutant_level_data.values() for _, p in values]
            metrics_suite, labels = compute_and_print_metrics(
                true_suite, pred_suite, False, threshold
            )
        # Case 2: test-suite level predictions
        else:
            metrics_suite, labels = compute_and_print_metrics(
                true_labels, predicted_labels, False
            )

        # Mutation score error
        mutation_scores, avg_mse = compute_and_print_mutation_score(mutant_level_data)
        metrics_suite["mutation_score_per_project"] = mutation_scores
        metrics_suite["error_average"] = avg_mse

        results_to_save["Test-suite"] = {"metrics": metrics_suite, "labels": labels}

        # Save the metrics in a CSV file if required
        if metrics_csv_file:
            if threshold is not None:
                metrics_csv_file = metrics_csv_file.replace(".csv", f"_th{threshold}.csv")
            save_metrics_csv(results_to_save, metrics_csv_file)

        return true_labels, predicted_labels, labels

    except FileNotFoundError:
        print(f"Error: The file {output_file} was not found.")
    except KeyError:
        print("Error: The file does not contain the columns 'Project', 'True Label' and 'Predicted Label'.")
    except Exception as e:
        print(f"Error while evaluating the model: {e}")


# Function to execute the ML script provided by the user
def execute_ml_script(ml_script, training_file, test_file, csv_predicted_name, seed):
    """
    Execute the external ML script and propagate the seed.

    The external script is expected to accept:
      --training_file
      --test_file
      --output_file
      --seed
    """
    try:
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = str(seed)

        command = [
            sys.executable, ml_script,
            "--training_file", training_file,
            "--test_file", test_file,
            "--output_file", csv_predicted_name,
            "--seed", str(seed)
        ]

        print(f"Running the ML script: {' '.join(command)}")
        subprocess.run(command, check=True, env=env)

        print(f"ML model executed successfully. Results saved to: {csv_predicted_name}")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while executing the ML script: {e}")
        raise


# Function to write the partitions into CSV files
def save_partitioned_datasets(train_data, val_data, test_data, columns,
                              csv_train_name, csv_val_name, csv_test_name):
    """
    Save the partitioned datasets (training, validation, test) into CSV files.

    :param train_data: Training data
    :param val_data: Validation data
    :param test_data: Test data
    :param columns: List of column headers
    :param csv_train_name: Name of the CSV file for training data
    :param csv_val_name: Name of the CSV file for validation data
    :param csv_test_name: Name of the CSV file for test data
    """
    # Write training data
    with open(csv_train_name, mode="w", newline="", encoding="utf-8") as train_file:
        writer = csv.writer(train_file)
        writer.writerow(columns)
        writer.writerows(train_data)

    # Write test data
    with open(csv_test_name, mode="w", newline="", encoding="utf-8") as test_file:
        writer = csv.writer(test_file)
        writer.writerow(columns)
        writer.writerows(test_data)

    # Write validation data if present
    if val_data:
        with open(csv_val_name, mode="w", newline="", encoding="utf-8") as val_file:
            writer = csv.writer(val_file)
            writer.writerow(columns)
            writer.writerows(val_data)

        print(
            "Processing completed. Training, validation and test CSV files generated: "
            f"{csv_train_name}, {csv_val_name} and {csv_test_name}"
        )
    else:
        print(
            "Processing completed. Training and test CSV files generated: "
            f"{csv_train_name} and {csv_test_name}"
        )


# Function to split instances into training/validation/test sets based on project lists
def partition_by_projects(projects_data, train_projects, val_projects, test_projects):
    """
    Perform partitioning based on project lists.

    :param projects_data: Set of mutants to be partitioned, grouped by project
    :param train_projects: List of projects for training
    :param val_projects: List of projects for validation
    :param test_projects: List of projects for testing
    """
    train_data, val_data, test_data = [], [], []

    # Append mutants from the specified projects
    for project_id in train_projects:
        train_data.extend(projects_data[project_id]["rows"])
    for project_id in (val_projects or []):
        val_data.extend(projects_data[project_id]["rows"])
    for project_id in test_projects:
        test_data.extend(projects_data[project_id]["rows"])

    return train_data, val_data, test_data


# Function to split instances into training/validation/test sets based on percentages
def partition_by_percentages(projects_data, training_p, val_p, test_p):
    """
    Perform partitioning based on provided percentages.

    :param projects_data: Set of mutants to be partitioned, grouped by project
    :param training_p: Percentage of instances to include in the training set
    :param val_p: Percentage of instances to include in the validation set
    :param test_p: Percentage of instances to include in the test set

    Note:
    Mutants from the same project are not split. A whole project is assigned to
    training, validation or test. A greedy approach is used: projects are sorted
    by mutant count (descending), and larger projects are added to the training
    set first, then validation (if specified), and the rest go to test.
    """
    total_mutants = sum(project["mutant_count"] for project in projects_data.values())
    print(f"Total number of mutants: {total_mutants}")

    # Number of mutants allowed in each partition
    training_limit = (training_p / 100) * total_mutants
    val_limit = (val_p / 100) * total_mutants if val_p else 0
    print(f"Training set limit (number of mutants): {training_limit}")
    if val_p:
        print(f"Validation set limit (mutants): {val_limit}")

    # Sort projects by number of mutants (descending), then by project name for stability
    sorted_projects = sorted(
        projects_data.items(),
        key=lambda x: (-x[1]["mutant_count"], x[0])
    )

    train_data, val_data, test_data = [], [], []
    assigned_projects = set()

    counts = {"training": 0, "validation": 0, "test": 0}

    for project_name, project_data in sorted_projects:
        project_mutants = project_data["rows"]
        project_count = project_data["mutant_count"]

        print(f"Mutants in project '{project_name}': {project_count}")

        # Add the whole project to training if within the training limit
        if counts["training"] + project_count <= training_limit:
            train_data.extend(project_mutants)
            counts["training"] += project_count
        elif val_p and counts["validation"] + project_count <= val_limit:
            val_data.extend(project_mutants)
            counts["validation"] += project_count
        else:
            test_data.extend(project_mutants)
            counts["test"] += project_count

        assigned_projects.add(project_name)

    # Any remaining unassigned projects go to test
    for project_name, project_data in sorted_projects:
        if project_name not in assigned_projects:
            test_data.extend(project_data["rows"])

    print(f"Mutants assigned to training: {len(train_data)}")
    if val_p:
        print(f"Mutants assigned to validation: {len(val_data)}")
    print(f"Mutants assigned to test: {len(test_data)}")

    return train_data, val_data, test_data


# Function to write the set of mutants to the output
def save_dataset(projects_data, columns, output_csv):
    """
    Save the mutants to a CSV file.

    :param projects_data: Set of mutants, grouped by project
    :param columns: Columns to be used as the CSV header
    :param output_csv: Name of the CSV file
    """
    with open(output_csv, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)

        # Sort by project name to keep output deterministic
        for project_name, project_data in sorted(projects_data.items(), key=lambda x: x[0]):
            rows = project_data["rows"]
            writer.writerows(rows)

    print(f"Processing completed. CSV generated: {output_csv}")


# Function to extract test cases and save them to a CSV file
def extract_testcases_to_csv(graph, output_test):
    """
    Process the TTL file by extracting test case information and generating an output CSV file.

    :param graph: Parsed RDF graph
    :param output_test: Output file name for the test case map CSV
    """
    testcases = []

    for subj in sorted(set(graph.subjects(RDF.type, PMTB.Test)), key=str):
        method_name = graph.value(subject=subj, predicate=PMTB.testMethodName)
        method_code = graph.value(subject=subj, predicate=PMTB.testMethodCode)
        if method_name and method_code:
            testcases.append({
                "TestMethod": str(method_name),
                "TestMethodCode": str(method_code)
            })

    if not testcases:
        print("No test cases found in the graph.")
        return

    with open(output_test, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["TestMethod", "TestMethodCode"])
        writer.writeheader()
        writer.writerows(testcases)


# Function to extract and filter mutants from a TTL file
def extract_filter_ttl_file(ttl_file, output_test, language, tool, blocks):
    """
    Extract and filter mutants from the projects in the TTL file according to the specified criteria.

    :param ttl_file: Path to the TTL file
    :param output_test: CSV file for generating test_map.csv if needed
    :param language: Programming language filter
    :param tool: Mutation tool filter
    :param blocks: List of data blocks to extract for each mutant
    """
    graph = Graph()
    graph.parse(ttl_file, format="turtle")

    rows = []

    for mutant in sorted(set(graph.subjects(predicate=PMTB.generatedByTool)), key=str):
        # Filter by language and tool
        file = graph.value(subject=mutant, predicate=PMTB.originalFile)
        if language and file:
            file_language = graph.value(subject=URIRef(file), predicate=SCHEMA.programmingLanguage)
            if file_language and str(file_language).lower() != language.lower():
                continue

        if tool:
            mutation_tool = graph.value(subject=mutant, predicate=PMTB.generatedByTool)
            mutation_tool_fragment = str(mutation_tool).split("#")[-1] if mutation_tool else ""
            if mutation_tool_fragment.lower() != tool.lower():
                continue

        # Extract basic mutant details
        original_program = graph.value(subject=mutant, predicate=PMTB.originalFile)
        project_uri = graph.value(subject=original_program, predicate=PMTB.partOfProject)
        project = str(project_uri).split("#")[-1]
        package = graph.value(subject=original_program, predicate=PMTB.package).toPython()
        file_name = graph.value(subject=original_program, predicate=PMTB.fileName).toPython()
        class_name = f"{package}.{file_name.rsplit('.', 1)[0]}"
        method = graph.value(subject=mutant, predicate=PMTB.method)
        line = graph.value(subject=mutant, predicate=PMTB.line)
        operator = graph.value(subject=mutant, predicate=PMTB.operator)

        # Get the label
        execution = graph.value(predicate=PMTB.executedOnMutant, object=mutant)
        label = None
        if execution:
            label = graph.value(subject=execution, predicate=PMTB.label)

        # Base CSV row
        row = [
            project,
            class_name,
            method,
            line.toPython() if line else "-",
            operator.toPython() if operator else "-",
            label.toPython() if label else "-"
        ]

        # Selected blocks
        if "execution" in blocks:
            if execution:
                for metric in dynamic_metrics.keys():
                    value = graph.value(subject=execution, predicate=getattr(PMTB, metric))
                    if value is None:
                        print(f"{mutant}: Missing value for {metric}")
                        row.append("-")
                    else:
                        if (value, RDF.first, None) in graph:
                            collection = Collection(graph, value)
                            py_list = [
                                item.toPython() if hasattr(item, "toPython") else str(item)
                                for item in collection
                            ]
                            row.append(str(py_list))
                        else:
                            row.append(value.toPython() if value is not None else "-")
            else:
                print(f"{mutant}: Missing execution block")
                for _ in dynamic_metrics.keys():
                    row.append("-")

        if "staticAnalysis" in blocks:
            static_analysis = graph.value(predicate=PMTB.analyzedMutant, object=mutant)
            if static_analysis:
                type_return = graph.value(subject=static_analysis, predicate=PMTB.typeReturn)
                row.append(type_return.toPython() if type_return else "-")

                for metric in static_metrics.keys():
                    value = graph.value(subject=static_analysis, predicate=getattr(PMTB, metric))
                    if value is None:
                        print(f"{mutant}: Missing value for {metric}")
                    row.append(value.toPython() if value is not None else "-")
            else:
                print(f"{mutant}: Missing static block")
                row.append("-")  # TypeReturn
                for _ in static_metrics.keys():
                    row.append("-")

        if "naturalLanguage" in blocks:
            nla = graph.value(predicate=PMTB.refersToMutant, object=mutant)
            if nla:
                # Iterate over test-related collections
                for t in tests.keys():
                    value = graph.value(subject=execution, predicate=getattr(PMTB, t))
                    if value is None:
                        print(f"{mutant}: Missing value for {t}")
                        row.append("-")
                    else:
                        try:
                            collection = Collection(graph, value)
                            testcases = list(collection)

                            method_names = []
                            for testcase_uri in testcases:
                                method_name = graph.value(subject=testcase_uri, predicate=PMTB.testMethodName)
                                if method_name:
                                    method_names.append(str(method_name))

                            row.append(str(method_names))
                        except Exception:
                            print(f"{mutant}: The value of {t} is not a list")
                            row.append("-")

                # Iterate over NLP metrics
                for metric in nl_metrics.keys():
                    value = graph.value(subject=nla, predicate=getattr(PMTB, metric))
                    if value is None:
                        row.append("-")
                        continue
                    else:
                        if (value, RDF.first, None) in graph:
                            collection = Collection(graph, value)
                            py_list = [
                                item.toPython() if hasattr(item, "toPython") else str(item)
                                for item in collection
                            ]
                            row.append(str(py_list))
                        else:
                            val_str = value.toPython()
                            if isinstance(val_str, str):
                                val_str = val_str.encode("unicode_escape").decode("utf-8")
                            row.append(val_str)
            else:
                print(f"{mutant}: Missing natural language block")
                for _ in tests.keys():
                    row.append("-")
                for _ in nl_metrics.keys():
                    row.append("-")

        rows.append(row)

    if rows and "naturalLanguage" in blocks:
        extract_testcases_to_csv(graph, output_test)

    return rows


# Function to process the different TTL files based on filters, extracting columns and data
def process_ttl_files(ttl_files, project_ids, output, language, tool, blocks):
    """
    Process the list of TTL files, where each project is represented by one TTL file.

    :param ttl_files: List of TTL files
    :param project_ids: List of project IDs
    :param output: Output path used to derive the test_map.csv location if needed
    :param language: Programming language filter
    :param tool: Mutation tool filter
    :param blocks: List of data blocks to extract for each mutant
    """
    projects_data = {}

    for ttl_file, project_id in zip(ttl_files, project_ids):
        project_name = ttl_file.split("/")[-1].replace(".ttl", "")

        output_test = Path(output).parent / f"{project_name}_test_map.csv"
        rows = extract_filter_ttl_file(ttl_file, output_test, language, tool, blocks)

        projects_data[project_id] = {"rows": rows, "mutant_count": len(rows)}

    # Dynamically determine which columns to include based on the selected blocks
    columns = ["Project", "Class", "Method", "Line", "Operator", "Label"]
    if "execution" in blocks:
        columns.extend(dynamic_metrics.keys())
    if "staticAnalysis" in blocks:
        columns.extend(["TypeReturn"])
        columns.extend(static_metrics.keys())
    if "naturalLanguage" in blocks:
        columns.extend(tests.values())
        columns.extend(nl_metrics.keys())

    return projects_data, columns


# Function to extract the paths of TTL files to be processed from the index
def extract_ttl_files(index_file, projects, citation):
    """
    Extract the paths of TTL files from the index TTL file.

    :param index_file: Index TTL file with the information of the projects
    :param projects: List of project identifiers to include, or None to include all
    :param citation: Citation identifier filter
    """
    graph = Graph()
    graph.parse(index_file, format="turtle")

    ttl_files = []
    project_ids = []
    index_file_path = Path(index_file)

    # Normalize project IDs to lowercase for comparison
    projects_set = set([p.lower() for p in projects]) if projects else None

    # If filtering by project list, verify that all requested projects exist in the index
    if projects_set:
        available_pr = {
            str(uri).split("#")[-1].lower()
            for uri in graph.subjects(predicate=SCHEMA.name)
        }
        missing_pr = projects_set - available_pr
        if missing_pr:
            print(f"The following projects were not found in the index: {', '.join(sorted(missing_pr))}")
            sys.exit(1)

    # Iterate over each project in a stable order
    for project_uri in sorted(set(graph.subjects(predicate=SCHEMA.name)), key=str):
        project_id = str(project_uri).split("#")[-1]

        # Filter by project list
        if projects_set and project_id.lower() not in projects_set:
            continue

        # Filter by citation
        if citation:
            paper = graph.value(subject=project_uri, predicate=SCHEMA.citation)
            paper_fragment = str(paper).strip("<>").split("#")[-1] if paper else ""
            if paper_fragment != citation:
                continue

        # Get the pm:ttlFile attribute
        ttl_file = graph.value(subject=project_uri, predicate=PMTB.ttlFile)
        if ttl_file:
            ttl_file_path = Path(ttl_file)
            combined_path = index_file_path.parent / ttl_file_path
            ttl_files.append(str(combined_path))
            project_ids.append(project_id)

    return ttl_files, project_ids


# Function to load configuration parameters from a configuration file
def load_config_file(config_path: str) -> dict:
    """
    Load YAML configuration file. Returns empty dict if no config is provided.
    
    :param config_path: Path to the YAML configuration file.
    """
    if not config_path:
        return {}

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Version check: ensures compatibility between the config file format and the current PMTBench version
    version = config.get("config_version", 1)
    if version != 1:
        raise ValueError(
            f"Unsupported config_version: {version}. Expected 1."
        )

    return config or {}

# Function to maintain CSV format
def to_csv(value):
    if value is None:
        return None
    if isinstance(value, list):
        return ",".join(map(str, value))
    return value


# Function to flatten the YAML configuration file
def flatten_config(cfg: dict) -> dict:
    """
    Convert nested YAML config into flat dictionary with keys matching CLI argument names.
    
    :param cfg: Parsed YAML configuration as a nested dictionary.
    """
    flat = {}

    # filters
    filters = cfg.get("filters", {})
    flat["language"] = filters.get("language")
    flat["tool"] = filters.get("tool")
    flat["citation"] = filters.get("citation")
    flat["projects"] = to_csv(filters.get("projects"))
    flat["blocks"] = filters.get("blocks")

    # reproducibility
    repro = cfg.get("reproducibility", {})
    flat["seed"] = repro.get("seed")

    # partitioning
    part = cfg.get("partitioning", {})
    flat["partition"] = to_csv(part.get("partition"))
    flat["train_projects"] = to_csv(part.get("train_projects"))
    flat["val_projects"] = to_csv(part.get("val_projects"))
    flat["test_projects"] = to_csv(part.get("test_projects"))
    flat["existing_data"] = part.get("existing_data")
    flat["training_file"] = part.get("training_file")
    flat["test_file"] = part.get("test_file")

    # ml
    ml = cfg.get("ml", {})
    flat["ml_script"] = ml.get("ml_script")
    flat["thresholds"] = to_csv(ml.get("thresholds"))

    # evaluation
    ev = cfg.get("evaluation", {})
    flat["confusion_matrix_file"] = ev.get("confusion_matrix_file")
    flat["metrics_csv_file"] = ev.get("metrics_csv_file")

    # io
    io = cfg.get("io", {})
    flat["index"] = io.get("index")
    flat["output"] = io.get("output")

    return flat


# Function to merge the parameters provided in the configuration file and command line.
def merge_config_and_args(args, cfg_flat: dict, parser) -> dict:
    """
    Merge CLI arguments with configuration file values.
    Priority order:
        1. Default values (argparse defaults)
        2. Configuration file (YAML)
        3. Command-line arguments (highest priority)

    :param args: Parsed command-line arguments (argparse Namespace).
    :param cfg_flat: Flattened configuration dictionary obtained from YAML.
    :param parser: Parser of args.
    """
    final = vars(args).copy()

    for key, value in cfg_flat.items():
        if value is None:
            continue

        cli_value = getattr(args, key, None)
        default_value = parser.get_default(key)

        # Case 1: CLI value is still default → YAML wins
        if cli_value == default_value:
            final[key] = value

        # Case 2: CLI explicitly provided → CLI wins
        else:
            final[key] = cli_value

    return final


# Function to parse the arguments
def parse_arguments():
    """
    Parse the command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Process mutants for use in ML models.")

    # Configuration file
    parser.add_argument("-cfg", "--config", type=str, default=None, help="Path to YAML configuration file.")

    # Arguments related to filters
    parser.add_argument("-l", "--language", type=str, help="Filter by programming language.")
    parser.add_argument("-t", "--tool", type=str, help="Filter by mutation tool.")
    parser.add_argument("-c", "--citation", type=str, help="Filter by citation source.")
    parser.add_argument(
        "-pr", "--projects", type=str, default=None,
        help="Comma-separated list of project IDs to filter. Example: 'proj1,proj2,proj3'"
    )
    parser.add_argument(
        "-b", "--blocks", type=str, nargs="*",
        choices=["staticAnalysis", "execution", "naturalLanguage"],
        default=["staticAnalysis", "execution", "naturalLanguage"],
        help="Select data blocks to include: staticAnalysis, execution, naturalLanguage."
    )

    # Global determinism
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Seed used to make this script deterministic and to propagate determinism to the external ML script."
    )

    # Arguments related to training/validation/test data and script execution
    parser.add_argument(
        "-p", "--partition", type=str, default=None,
        help="Partition percentages in the format 'training,test' or 'training,validation,test'. "
             "Examples: 80,20 or 70,15,15. Values must sum to 100."
    )
    parser.add_argument(
        "-trp", "--train-projects", type=str, default=None,
        help="Comma-separated list of project IDs for the training set. Example: 'proj1,proj2,proj3'"
    )
    parser.add_argument(
        "-vap", "--val-projects", type=str, default=None,
        help="Comma-separated list of project IDs for the validation set. Example: 'proj1,proj2,proj3'"
    )
    parser.add_argument(
        "-tep", "--test-projects", type=str, default=None,
        help="Comma-separated list of project IDs for the test set. Example: 'proj1,proj2,proj3'"
    )
    parser.add_argument(
        "-e", "--existing_data", action="store_true",
        help="Use existing training and test CSV files."
    )
    parser.add_argument(
        "-tr", "--training_file", type=str,
        help="Path to the training CSV file (required if --existing_data is used)."
    )
    parser.add_argument(
        "-te", "--test_file", type=str,
        help="Path to the test CSV file (required if --existing_data is used)."
    )
    parser.add_argument(
        "-m", "--ml_script", type=str, default=None,
        help=(
            "Path to a Python script that runs the ML model. "
            "It must accept the following arguments: "
            "--training_file (path to training CSV file), "
            "--test_file (path to test CSV file), "
            "--output_file (path to output CSV file for results), "
            "--seed (integer seed). "
            "The output CSV file must contain one row per instance, with the columns: "
            "'Project', 'True Label', 'Predicted Label' and, optionally, "
            "'Killing Probability' (with these exact names)."
        )
    )
    parser.add_argument(
        "-th", "--thresholds", type=str, default=None,
        help="Comma-separated list of thresholds for aggregating predictions. Example: 0.10,0.25,0.5"
    )

    # Arguments related to evaluation output
    parser.add_argument(
        "-cm", "--confusion_matrix_file", type=str, default=None,
        help="Filename to save the confusion matrix image (e.g., matrix.png)"
    )
    parser.add_argument(
        "-mc", "--metrics_csv_file", type=str, default=None,
        help="Filename to save metrics as CSV (e.g., metrics.csv)"
    )

    # Arguments related to input/output
    parser.add_argument("-i", "--index", type=str, default="index.ttl", help="Path to the index.ttl file.")
    parser.add_argument("-o", "--output", type=str, default="output.csv", help="Name of the output CSV file.")

    # Parse arguments
    args = parser.parse_args()

    # Load configuration file (if any), flatten the file, and merge
    cfg = load_config_file(args.config)
    cfg_flat = flatten_config(cfg)
    merged = merge_config_and_args(args, cfg_flat, parser)
    args = argparse.Namespace(**merged)

    # Set determinism
    set_global_determinism(args.seed)

    # Parse lists of projects
    args.projects = [p.strip() for p in args.projects.split(",")] if args.projects else None
    args.train_projects = [p.strip() for p in args.train_projects.split(",")] if args.train_projects else None
    args.val_projects = [p.strip() for p in args.val_projects.split(",")] if args.val_projects else None
    args.test_projects = [p.strip() for p in args.test_projects.split(",")] if args.test_projects else None

    # Parse thresholds
    if args.thresholds:
        try:
            args.thresholds = [float(x) for x in args.thresholds.split(",")]
        except ValueError:
            parser.error("Thresholds must be a comma-separated list of floats, e.g., 0.10,0.25,0.5")

    # Validate combinations of existing_data and ml_script
    try:
        if args.existing_data:
            if not args.training_file or not args.test_file:
                raise ValueError("When using --existing_data, training and test CSV files must be specified.")
            if args.language or args.tool or args.citation or args.projects or args.partition \
               or args.train_projects or args.test_projects or args.val_projects:
                raise ValueError("Filters or partitioning should not be used together with --existing_data.")

        if not args.existing_data:
            if args.ml_script and not (args.partition or args.train_projects):
                raise ValueError("Partition or existing data must be specified when using an ML script.")

        if not args.ml_script and (args.confusion_matrix_file or args.metrics_csv_file):
            raise ValueError("Evaluation output arguments (--confusion_matrix_file and --metrics_csv_file) "
                             "should only be specified when using an ML script.")

        if not args.ml_script and args.thresholds:
            raise ValueError("Thresholds should only be specified when using an ML script.")
    except ValueError as e:
        print(f"Argument combination error: {e}")
        sys.exit(1)

    # Validate train/test/validation project rules
    try:
        if args.projects and args.train_projects:
            raise ValueError(
                "Cannot use --projects together with --train-projects/--val-projects/--test-projects; "
                "manual partitioning already selects the projects to include."
            )

        if (args.train_projects and not args.test_projects) or (args.test_projects and not args.train_projects):
            raise ValueError("When using --train-projects, --test-projects must be specified as well (and vice versa).")

        if args.val_projects and not (args.train_projects and args.test_projects):
            raise ValueError("When using --val-projects, --train-projects and --test-projects must also be specified.")

        if args.train_projects and args.test_projects:
            train_set = set(args.train_projects)
            test_set = set(args.test_projects)
            val_set = set(args.val_projects) if args.val_projects else set()
            intersection = (train_set & test_set) | (train_set & val_set) | (test_set & val_set)
            if intersection:
                raise ValueError(f"Projects appearing in more than one partition: {', '.join(sorted(intersection))}")

        if args.partition and (args.train_projects or args.test_projects or args.val_projects):
            raise ValueError("Do not use --partition with --train-projects/--val-projects/--test-projects.")
    except ValueError as e:
        print(f"Argument combination error: {e}")
        sys.exit(1)

    # Process and validate the partition argument
    if args.partition:
        try:
            parts = list(map(int, args.partition.split(",")))
            if len(parts) not in [2, 3]:
                raise ValueError("Partition must have 2 or 3 comma-separated integers.")

            if sum(parts) != 100:
                raise ValueError("The percentages must add up to 100.")

            if len(parts) == 2:
                args.training_p, args.test_p = parts
                args.val_p = 0
            else:
                args.training_p, args.val_p, args.test_p = parts
        except ValueError as e:
            print(f"Partition argument error: {e}")
            sys.exit(1)
    else:
        args.training_p = None
        args.val_p = None
        args.test_p = None

    return args


# Main execution
if __name__ == "__main__":
    """
    Functionalities according to the indicated parameters:

    1) Filtering mode:
       If -l/-t/-c/-pr/-b is specified, a single output file is created with all
       mutants matching the filters.

       Example:
       python3 main.py -i index.ttl -b staticAnalysis execution -t PIT_1.15.8 -l java -o output.csv

    2) Automated partition by percentages:
       If -p is specified, percentages for splitting the output dataset can be provided:
       * Two values: training and test (e.g., "80,20")
       * Three values: training, validation, and test (e.g., "70,15,15")

       Examples:
       python3 main.py -i index.ttl -l java -b execution -t PIT_1.15.8 -o o_7030.csv -p 70,30
       python3 main.py -i index.ttl -l java -b execution -t PIT_1.15.8 -o o_701515.csv -p 70,15,15

    3) Manual partition by project IDs:
       Projects can be explicitly assigned to partitions using:
       -trp: training projects
       -vap: validation projects (optional)
       -tep: test projects

    4) ML script execution:
       If -m is specified, in addition to the training/validation/test files, a
       prediction file is created with the results of the provided script execution.

       Example:
       python3 main.py -i index.ttl -l java -b execution -t PIT_1.15.8 -o o_7030.csv -p 70,30 -m randomForest.py --seed 42

    5) Using existing training/test files:
       If --existing_data is specified, only the provided script will be executed
       based on existing training (-tr) and test (-te) files.

       Example:
       python3 main.py --existing_data -tr o_7030_training.csv -te o_7030_test.csv -m randomForest.py --seed 42

    6) Evaluation:
       If -cm is specified, the confusion matrix will be saved in the indicated file.
       If -mc is specified, the metrics will be saved in the indicated CSV file.

       If -th is specified and killing probabilities exist, test-case level
       predictions will be aggregated at the test-suite level and evaluation
       metrics will be reported for each provided threshold.
    """
    args = parse_arguments()

    print("Provided arguments:")
    print(f"Seed: {args.seed}")

    if not args.existing_data:
        print(f"Index: {args.index}")
        print(f"Language: {args.language}")
        print(f"Tool: {args.tool}")
        print(f"Citation: {args.citation}")
        print(f"Projects: {args.projects}")
        print(f"Selected blocks: {args.blocks}")

        if args.train_projects:
            print("Manual partition assignment provided:")
            print(f"  Train projects: {getattr(args, 'train_projects', None)}")
            print(f"  Validation projects: {getattr(args, 'val_projects', None)}")
            print(f"  Test projects: {getattr(args, 'test_projects', None)}")
        else:
            if args.training_p:
                print("Percentage-based partition provided:")
                if args.val_p is not None:
                    print(f"Training: {args.training_p}%, Validation: {args.val_p}%, Test: {args.test_p}%")
                else:
                    print(f"Training: {args.training_p}%, Test: {args.test_p}%")
            else:
                print("No partitioning option provided.")
    else:
        print(f"Training/Test files: {args.training_file} - {args.test_file}")

    print(f"Output file: {args.output}")
    if args.ml_script:
        print(f"Script: {args.ml_script}")
        if args.thresholds:
            print(f"Thresholds: {args.thresholds}")
        print(f"Metrics CSV output: {args.metrics_csv_file}")
        print(f"Confusion matrix output: {args.confusion_matrix_file}")

    base_output_name = args.output.replace(".csv", "")

    # First, if required, process the TTL files to extract mutant info
    if not args.existing_data:
        # Determine which projects must be extracted from the index
        if args.train_projects:
            projects = []
            projects.extend(args.train_projects)
            if args.val_projects:
                projects.extend(args.val_projects)
            if args.test_projects:
                projects.extend(args.test_projects)
        else:
            projects = args.projects

        ttl_files, project_ids = extract_ttl_files(args.index, projects, args.citation)

        if len(ttl_files) == 0:
            print("No TTL files found to process.")
            sys.exit(1)
        else:
            print("TTL files found:")
            for ttl_file in ttl_files:
                print(ttl_file)

        # Process project information based on the provided arguments
        pr_data, cols = process_ttl_files(
            ttl_files, project_ids, args.output, args.language, args.tool, args.blocks
        )

        # Write the output, performing partitioning depending on the provided arguments
        if not args.training_p and not args.train_projects:
            save_dataset(pr_data, cols, args.output)
        else:
            csv_train_name = f"{base_output_name}_training.csv"
            csv_validation_name = f"{base_output_name}_validation.csv"
            csv_test_name = f"{base_output_name}_test.csv"

            if args.training_p:
                train_data, val_data, test_data = partition_by_percentages(
                    pr_data, args.training_p, args.val_p, args.test_p
                )
            else:
                train_data, val_data, test_data = partition_by_projects(
                    pr_data, args.train_projects, args.val_projects, args.test_projects
                )

            save_partitioned_datasets(
                train_data, val_data, test_data, cols,
                csv_train_name, csv_validation_name, csv_test_name
            )

    # If the ML model execution script is provided, run it and evaluate the results
    if args.ml_script:
        csv_predicted_name = f"{base_output_name}_predicted.csv"

        # If external files were provided, use them here
        if args.training_file:
            csv_train_name = args.training_file
            csv_test_name = args.test_file

        execute_ml_script(
            args.ml_script,
            csv_train_name,
            csv_test_name,
            csv_predicted_name,
            args.seed
        )

        if args.thresholds:
            for th in args.thresholds:
                true_labs, pred_labs, labs = evaluate_model(
                    csv_predicted_name, args.metrics_csv_file, th
                )
        else:
            true_labs, pred_labs, labs = evaluate_model(
                csv_predicted_name, args.metrics_csv_file
            )

        # Plot the confusion matrix if required
        if args.confusion_matrix_file:
            plot_confusion_matrix(true_labs, pred_labs, labs, args.confusion_matrix_file)