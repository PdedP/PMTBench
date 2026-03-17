### Data split

#### Traditional partitioning:

1) To split the data with citation `'pmtbenchAL'` into *80% training* and *20% test*, you can run:
```
python3 main.py -i DataSplitExample/index.ttl -p 80,20 -c pmtbenchAL -b execution staticAnalysis -o DataSplitExample/split_8020.csv
```

2) To split the data with citation `'pmtbenchAL'` into *70% training*, *15% validation*, and *15% test*, use:
```
python3 main.py -i DataSplitExample/index.ttl -p 70,15,15 -c pmtbenchAL -b execution staticAnalysis -o DataSplitExample/split_701515.csv
```
#### Partitioning by projects:
```
python3 main.py -i DataSplitExample/index.ttl -trp  Csv_1,Csv_5 -tep Csv_10 -b naturalLanguage -o DataSplitExample/split_Csv.csv
```
