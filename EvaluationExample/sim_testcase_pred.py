import argparse
import pandas as pd
import random
import ast

def main():
    parser = argparse.ArgumentParser(description="Simulate predictions for mutation testing at test-case level")
    parser.add_argument("--training_file", type=str, required=True, help="Path to the training CSV file")
    parser.add_argument("--test_file", type=str, required=True, help="Path to the test CSV file")
    parser.add_argument("--output_file", type=str, required=True, help="Path to output results CSV file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")

    args = parser.parse_args()

    random.seed(args.seed)

    # Load data (we do not actually use training_file, just to keep consistent structure)
    train_data = pd.read_csv(args.training_file)
    test_data = pd.read_csv(args.test_file)

    # We expect the test_file to have these columns: Tests and KillingTests
    executed_col = "Tests"
    killed_col = "KillingTests"

    output_rows = []

    for idx, row in test_data.iterrows():
        project = row["Project"]

        # Parse the lists (string to list)
        executed_tests = ast.literal_eval(row[executed_col]) if pd.notna(row[executed_col]) else []
        killed_tests = ast.literal_eval(row[killed_col]) if pd.notna(row[killed_col]) else []

        # True labels: KILLED if test in KillingTests, else SURVIVED
        true_labels = ["KILLED" if t in killed_tests else "SURVIVED" for t in executed_tests]

        # Predicted labels: random generation of same length
        predicted_labels = [random.choice(["KILLED", "SURVIVED"]) for _ in executed_tests]

        # Add row
        output_rows.append({
            "Project": project,
            "True Label": str(true_labels),
            "Predicted Label": str(predicted_labels)
        })

    # Save results
    results_df = pd.DataFrame(output_rows)
    results_df.to_csv(args.output_file, index=False)

    print(f"Simulation results written to {args.output_file}")

if __name__ == "__main__":
    main()
