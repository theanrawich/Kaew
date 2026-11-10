"""Generate local synthetic WAVs from the supplied reference manifest."""
import argparse
import json
from pathlib import Path
from audio_service import MmsThaiTTS

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--out',required=True)
    args=p.parse_args(); out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(Path(__file__).with_name('asr_commands.json').read_text(encoding='utf-8'))
    tts=MmsThaiTTS(args.model)
    for case in manifest['cases']:
        (out/case['audio']).write_bytes(tts.synthesize(case['text']))
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Generated %d synthetic WAVs; not human speech.'%len(manifest['cases']))

if __name__=='__main__':main()
