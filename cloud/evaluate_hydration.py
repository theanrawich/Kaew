"""Reproducible small advisory model smoke evaluation, not clinical validation."""
import argparse
import json
import time
from hydration_ai import TransformersProvider, recommend

CASES = [
    {'goal_ml':2000,'drank_ml':600,'minutes_since_drink':90,'cup_ml':20,'profile':'balanced'},
    {'goal_ml':2000,'drank_ml':1800,'minutes_since_drink':10,'cup_ml':200,'profile':'gentle'},
    {'goal_ml':2000,'drank_ml':0,'minutes_since_drink':None,'cup_ml':None,'profile':'active'},
]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',required=True)
    args=parser.parse_args()
    provider=TransformersProvider(args.model)
    for context in CASES:
        started=time.monotonic()
        try:
            raw=provider(context)
            result=recommend(context,lambda _:raw)
            error=None
        except Exception as exc:
            raw=None
            result=recommend(context,None)
            error=type(exc).__name__
        print(json.dumps({'context':context,'raw':raw,'result':result,'error':error,
                          'seconds':round(time.monotonic()-started,3)},ensure_ascii=False))

if __name__=='__main__': main()
