### Evaluation of PMT models

#### Test-suite level prediction

- Execution of `decision_tree.py` implementing a decision tree model:
```
python3 EvaluationExample/decision_tree.py --training_file EvaluationExample/output_training.csv --test_file EvaluationExample/output_test.csv --output_file EvaluationExample/predicted_labels.csv
```

- Execution and evaluation of the decision tree model with PMTBench (execution block, citation 'pmtbenchAL' and partition 80% training-20% test):
```
python3 pmtbench.py -i EvaluationExample/index.ttl -p 80,20 -c pmtbenchAL -b execution -o EvaluationExample/split_8020.csv --ml_script EvaluationExample/decision_tree.py
```

- Evaluation of the decision tree model with existing data:
```
python3 pmtbench.py --existing_data -tr EvaluationExample/output_training.csv -te EvaluationExample/output_test.csv -o EvaluationExample/output.csv -m EvaluationExample/decision_tree.py -cm EvaluationExample/matrix-dt.png -mc EvaluationExample/metrics-dt.csv
```

You can also run these examples using the configuration files:
```
python3 pmtbench.py -cfg EvaluationExample/pmtbench-eval-ts1.yml
python3 pmtbench.py -cfg EvaluationExample/pmtbench-eval-ts2.yml
```

#### Test-case level prediction

- Execution of `sim_testcase_pred.py` implementing a simulated prediction model at the test-case level (only labels, no killing probabilities):
```
python3 EvaluationExample/sim_testcase_pred.py --training_file EvaluationExample/output_testcase_training.csv --test_file EvaluationExample/output_testcase_test.csv --output_file EvaluationExample/predicted_testcase_labels.csv
```

- Execution and evaluation of the simulated model with PMTBench (naturalLanguage block and partitioning by projects, with Csv_1 used for training and Csv_5 for test):
```
python3 pmtbench.py -i EvaluationExample/index.ttl -trp Csv_1 -tep Csv_5 -b naturalLanguage -o EvaluationExample/split_Csv_1_5.csv --ml_script EvaluationExample/sim_testcase_pred.py
```

- Evaluation of the simulated model with existing data:
```
python3 pmtbench.py --existing_data -tr EvaluationExample/output_testcase_training.csv -te EvaluationExample/output_testcase_test.csv -o EvaluationExample/output_testcase.csv -m EvaluationExample/sim_testcase_pred.py -cm EvaluationExample/matrix-sm.png -mc EvaluationExample/metrics-sm.csv
```

- Execution and evaluation of `sim_testcase_pred_prob.py` implementing a simulated prediction model at the test-case level, including both labels and killing probabilities. Test-case results are aggregated at the test-suite level using two different thresholds (0.1 and 0.25):
```
python3 pmtbench.py -i EvaluationExample/index.ttl -trp Csv_1 -tep Csv_5 -b naturalLanguage -o EvaluationExample/split_Csv_1_5_prob.csv --ml_script EvaluationExample/sim_testcase_pred_prob.py -mc EvaluationExample/metrics-smp.csv -th 0.1,0.25
```

You can also run these examples using the configuration files:
```
python3 pmtbench.py -cfg EvaluationExample/pmtbench-eval-tc1.yml
python3 pmtbench.py -cfg EvaluationExample/pmtbench-eval-tc2.yml
python3 pmtbench.py -cfg EvaluationExample/pmtbench-eval-tc3.yml

```


