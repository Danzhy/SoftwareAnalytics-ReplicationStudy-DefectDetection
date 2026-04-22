import json, random
with open("../data/detailed-database/overall.json") as f:
    data = json.load(f)
sample = random.Random(42).sample(data, 10)

for elem in sample:
    print(elem["id"])