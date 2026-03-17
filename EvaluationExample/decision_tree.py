import argparse
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score

def main():
    parser = argparse.ArgumentParser(description="Train and evaluate a DecisionTreeClassifier")
    parser.add_argument("--training_file", type=str, required=True, help="Path to the training CSV file")
    parser.add_argument("--test_file", type=str, required=True, help="Path to the test CSV file")
    parser.add_argument("--output_file", type=str, required=True, help="Path to output results CSV file")
    
    args = parser.parse_args()

    # Load data
    train_data = pd.read_csv(args.training_file)
    test_data = pd.read_csv(args.test_file)
    
    project = test_data["Project"]

    # Prepare training and test sets
    X_train = train_data.drop(columns=["Label","Project","Class","Method","Line","Operator"])
    y_train = train_data["Label"]
    X_test = test_data.drop(columns=["Label","Project","Class","Method","Line","Operator"])
    y_test = test_data["Label"]

    # Train the model
    model = DecisionTreeClassifier(random_state=42)
    model.fit(X_train, y_train)

    # Make predictions
    predictions = model.predict(X_test)

    # Save results
    results = pd.DataFrame({
        "Project": project,
        "True Label": y_test,
        "Predicted Label": predictions
    })
    results.to_csv(args.output_file, index=False)

    print(f"Results written to {args.output_file}")

if __name__ == "__main__":
    main()
