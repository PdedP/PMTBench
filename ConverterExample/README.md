### Conversion

> **Note:** remove or rename the index file `index.ttl` before executing the following scenarios.

- **Scenario 1:** AL channel and test suite granularity
```
python3 global_converter.py --projects_dir ConverterExample/AL/Projects-CSV --projects_csv ConverterExample/AL/projects-common.csv --output_dir ConverterExample/AL/Projects-TTL --index_file ConverterExample/AL/index.ttl
```

- **Scenario 2:** NL channel and test case granularity
```
python3 global_converter.py --projects_dir ConverterExample/NL-tc/Projects-CSV --projects_csv ConverterExample/NL-tc/projects-common.csv --output_dir ConverterExample/NL-tc/Projects-TTL --index_file ConverterExample/NL-tc/index.ttl
```

> **Note:** The execution of this scenario will print some blocks like the following one:

[INFO] Adding missing tests to test_paths: {'org.apache.commons.csv.CSVFileParserTest.testCSVFile.4', 'org.apache.commons.csv.CSVFileParserTest.testCSVFile.5', 'org.apache.commons.csv.CSVFileParserTest.testCSVFile.0'}
No test_id for: org.apache.commons.csv.CSVFileParserTest.testCSVFile.4
No test_id for: org.apache.commons.csv.CSVFileParserTest.testCSVFile.5
No test_id for: org.apache.commons.csv.CSVFileParserTest.testCSVFile.0
[ERROR] No valid test results for mutant Csv_5_org.apache.commons.csv.CSVFormat.java_585_STD_205.
Skipping mutant Csv_5_org.apache.commons.csv.CSVFormat.java_585_STD_205 due to inconsistent execution data.

This is because:
- Some test cases in KillingTests are not included in the column Tests, so the converter repairs the list of Tests adding those missing tests to the list. 
- Then the converter detects that those tests have no data in the test map distributed with the dataset, so they are removed. 
- In some mutants, after removing those test cases, the list of killing test cases becomes empty. If the list of passing tests is also empty, the mutant is not converted to avoid inconsistencies.


- **Scenario 3**: AL and NL channel (BOTH) and test case granularity
```
python3 global_converter.py --projects_dir ConverterExample/BOTH-tc/Projects-CSV --projects_csv ConverterExample/BOTH-tc/projects-common.csv --output_dir ConverterExample/BOTH-tc/Projects-TTL --index_file ConverterExample/BOTH-tc/index.ttl
```
