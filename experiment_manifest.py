
import csv
import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path

import yaml


_PATH_ARGUMENTS = {
    "config",
    "index",
    "output",
    "training_file",
    "test_file",
    "ml_script",
    "model_config",
    "confusion_matrix_file",
    "metrics_csv_file",
}


_DERIVED_ARGUMENTS = {"training_p", "val_p", "test_p", "seed"}


_EXISTING_DATA_NOT_APPLIED = {
    "index",
    "language",
    "tool",
    "citation",
    "projects",
    "blocks",
    "partition",
    "train_projects",
    "val_projects",
    "test_projects",
}


def _sha256(file_path):
    """Calculate the SHA-256 hash of a file.

    :param file_path: Path to the file to hash
    """
    if not file_path or not Path(file_path).is_file():
        return None

    digest = hashlib.sha256()
    with open(file_path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(file_path, repo_dir):
    """Return the path used to identify a file in the experiment manifest.

    :param file_path: Path to the file
    :param repo_dir: Root directory of the PMTBench repository
    """
    if not file_path:
        return None

    raw = Path(file_path)
    try:
        resolved = raw.resolve()
        root = Path(repo_dir).resolve()
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:


            return raw.name
    except (OSError, RuntimeError):
        return raw.name


def _file_info(file_path, repo_dir):
    """Collect the manifest path and SHA-256 hash of a file.

    :param file_path: Path to the file
    :param repo_dir: Root directory of the PMTBench repository
    """
    if not file_path or not Path(file_path).is_file():
        return None
    return {
        "path": _manifest_path(file_path, repo_dir),
        "sha256": _sha256(file_path),
    }


def _partition_info(file_path, repo_dir):
    """Collect file information and partition composition.

    :param file_path: Path to the partition CSV file
    :param repo_dir: Root directory of the PMTBench repository
    """
    info = _file_info(file_path, repo_dir)
    if info is None:
        return None

    projects = set()
    instances = 0
    with open(file_path, "r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        has_project = reader.fieldnames is not None and "Project" in reader.fieldnames
        for row in reader:
            instances += 1
            if has_project and row.get("Project"):
                projects.add(row["Project"])

    info["instances"] = instances
    info["projects"] = sorted(projects)
    return info


def _git_value(repo_dir, *args):
    """Obtain a value from the PMTBench Git repository.

    :param repo_dir: Root directory of the PMTBench repository
    :param args: Arguments passed to the Git command
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def _load_yaml(file_path):
    """Load a YAML file.

    :param file_path: Path to the YAML file
    """
    if not file_path or not Path(file_path).is_file():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as file_obj:
            return yaml.safe_load(file_obj)
    except (OSError, yaml.YAMLError):
        return None


def _capture_environment(base_output, repo_dir):
    """Capture the execution environment and installed package versions.

    :param base_output: Base path used to generate the environment snapshot
    :param repo_dir: Root directory of the PMTBench repository
    """
    environment_file = f"{base_output}_environment.txt"
    capture_status = "captured"

    try:


        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "list",
                "--format=freeze",
                "--disable-pip-version-check",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        package_output = result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        capture_status = "unavailable"
        package_output = "Python package snapshot unavailable.\n"

    snapshot = None
    try:
        with open(environment_file, "w", encoding="utf-8") as file_obj:
            file_obj.write(package_output)
        snapshot = _file_info(environment_file, repo_dir)
    except OSError:
        snapshot = None

    return {
        "python": {
            "version": sys.version.split()[0],
            "implementation": platform.python_implementation(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "dependencies": {
            "capture": capture_status,
            "snapshot": snapshot,
        },
    }


def _model_info(args, repo_dir):
    """Collect information about the ML model and its configuration.

    :param args: Parsed PMTBench arguments
    :param repo_dir: Root directory of the PMTBench repository
    """
    if not args.ml_script:
        return None

    implementation = _file_info(args.ml_script, repo_dir)
    if implementation is None:
        implementation = {
            "path": _manifest_path(args.ml_script, repo_dir),
            "sha256": None,
        }

    model = {"implementation": implementation}

    if getattr(args, "model_config", None):
        configuration = _file_info(args.model_config, repo_dir)
        if configuration is None:
            configuration = {
                "path": _manifest_path(args.model_config, repo_dir),
                "sha256": None,
            }
        parameters = _load_yaml(args.model_config)
        if parameters is not None:
            configuration["parameters"] = parameters
        model["configuration"] = configuration

    return model


def _clean_value(value, repo_dir, key=None):
    """Prepare an argument value for inclusion in the experiment manifest.

    :param value: Argument value to process
    :param repo_dir: Root directory of the PMTBench repository
    :param key: Name of the argument being processed
    """
    if key in _PATH_ARGUMENTS and isinstance(value, str):
        return _manifest_path(value, repo_dir)
    if isinstance(value, list):
        return [_clean_value(item, repo_dir) for item in value]
    return value


def _effective_arguments(args, repo_dir):
    """Collect the effective arguments used in the PMTBench execution.

    :param args: Parsed PMTBench arguments
    :param repo_dir: Root directory of the PMTBench repository
    """
    cleaned = {}
    existing_data = bool(getattr(args, "existing_data", False))

    for key, value in vars(args).items():
        if key in _DERIVED_ARGUMENTS:
            continue
        if existing_data and key in _EXISTING_DATA_NOT_APPLIED:
            continue
        if value is None:
            continue
        if value is False:
            continue
        if isinstance(value, (list, tuple, dict, str)) and len(value) == 0:
            continue

        cleaned[key] = _clean_value(value, repo_dir, key=key)

    return cleaned


def _dataset_info(args, repo_dir):
    """Collect information about the dataset used in the execution.

    :param args: Parsed PMTBench arguments
    :param repo_dir: Root directory of the PMTBench repository
    """
    if args.existing_data:
        return {"source": "existing_data"}

    dataset = {
        "index": _manifest_path(args.index, repo_dir),
    }
    if args.citation:
        dataset["citation"] = args.citation

    filters = {}
    for key in ("language", "tool", "projects", "blocks"):
        value = getattr(args, key, None)
        if value is not None and value != []:
            filters[key] = value
    if filters:
        dataset["filters"] = filters

    return dataset


def save_experiment_manifest(args, pmtbench_script):
    """Generate and save the experiment provenance manifest.

    :param args: Parsed PMTBench arguments used in the execution
    :param pmtbench_script: Path to the PMTBench script executed
    """
    base_output = args.output.replace(".csv", "")
    manifest_file = f"{base_output}_manifest.yml"
    repo_dir = Path(pmtbench_script).resolve().parent

    if args.existing_data:
        strategy = "existing_data"
        partition_files = {
            "training": args.training_file,
            "validation": None,
            "test": args.test_file,
        }
    elif args.training_p:
        strategy = "random_project_percentages"
        partition_files = {
            "training": f"{base_output}_training.csv",
            "validation": f"{base_output}_validation.csv",
            "test": f"{base_output}_test.csv",
        }
    elif args.train_projects:
        strategy = "manual_projects"
        partition_files = {
            "training": f"{base_output}_training.csv",
            "validation": f"{base_output}_validation.csv",
            "test": f"{base_output}_test.csv",
        }
    else:
        strategy = "none"
        partition_files = {}

    resolved = {}
    for name, file_path in partition_files.items():
        info = _partition_info(file_path, repo_dir)
        if info is not None:
            resolved[name] = info

    partition = {
        "strategy": strategy,
        "resolved": resolved,
    }
    if args.training_p:
        partition["requested_percentages"] = {
            "training": args.training_p,
            "validation": args.val_p,
            "test": args.test_p,
        }

    outputs = {}
    if not args.existing_data:
        if strategy == "none":
            info = _file_info(args.output, repo_dir)
            if info:
                outputs["dataset"] = info
        else:
            for name, file_path in partition_files.items():
                info = _file_info(file_path, repo_dir)
                if info:
                    outputs[name] = info

    predicted_file = f"{base_output}_predicted.csv" if args.ml_script else None
    info = _file_info(predicted_file, repo_dir)
    if info:
        outputs["predictions"] = info

    if args.metrics_csv_file:
        metrics = []
        if args.thresholds:
            candidates = [
                args.metrics_csv_file.replace(".csv", f"_th{threshold}.csv")
                for threshold in args.thresholds
            ]
        else:
            candidates = [args.metrics_csv_file]
        for candidate in candidates:
            info = _file_info(candidate, repo_dir)
            if info:
                metrics.append(info)
        if metrics:
            outputs["metrics"] = metrics

    info = _file_info(args.confusion_matrix_file, repo_dir)
    if info:
        outputs["confusion_matrix"] = info

    pmtbench_info = {
        "script": Path(pmtbench_script).name,
        "script_sha256": _sha256(pmtbench_script),
    }
    version = _git_value(repo_dir, "describe", "--tags", "--always", "--dirty")
    commit = _git_value(repo_dir, "rev-parse", "HEAD")
    if version is not None:
        pmtbench_info["version"] = version
    if commit is not None:
        pmtbench_info["git_commit"] = commit

    manifest = {
        "pmtbench": pmtbench_info,
        "execution": {
            "seed": args.seed,
            "effective_arguments": _effective_arguments(args, repo_dir),
        },
        "environment": _capture_environment(base_output, repo_dir),
        "dataset": _dataset_info(args, repo_dir),
        "partition": partition,
        "model": _model_info(args, repo_dir),
        "outputs": outputs,
    }


    manifest = {key: value for key, value in manifest.items() if value not in (None, {}, [])}

    with open(manifest_file, "w", encoding="utf-8") as file_obj:
        yaml.safe_dump(manifest, file_obj, sort_keys=False, allow_unicode=True)

    print(f"Experiment manifest saved to {_manifest_path(manifest_file, repo_dir)}")
