import argparse
from pathlib import Path

import pandas as pd
import yaml
from sklearn.metrics import accuracy_score
from sklearn.tree import DecisionTreeClassifier


def load_model_parameters(path):
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return dict(cfg.get("parameters") or {})


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate a DecisionTreeClassifier")
    parser.add_argument("--training_file", type=str, required=True)
    parser.add_argument("--test_file", type=str, required=True)
    parser.add_argument("--output_file", type=str, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model_config", type=str, default=None)
    args = parser.parse_args()

    train_data = pd.read_csv(args.training_file)
    test_data = pd.read_csv(args.test_file)
    project = test_data["Project"]

    drop_cols = ["Label", "Project", "Class", "Method", "Line", "Operator"]
    X_train = train_data.drop(columns=drop_cols)
    y_train = train_data["Label"]
    X_test = test_data.drop(columns=drop_cols)
    y_test = test_data["Label"]

    params = load_model_parameters(args.model_config)
    params["random_state"] = args.seed
    model = DecisionTreeClassifier(**params)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    pd.DataFrame({
        "Project": project,
        "True Label": y_test,
        "Predicted Label": predictions,
    }).to_csv(args.output_file, index=False)

    print(f"Results written to {args.output_file}")
    print(f"Accuracy: {accuracy_score(y_test, predictions):.6f}")
    print(f"Seed used: {args.seed}")
    if args.model_config:
        print(f"Model config: {Path(args.model_config).name}")


if __name__ == "__main__":
    main()
