"""Dependency-injected speech pipeline. Providers must be supplied by the caller."""

class VoicePipeline:
    def __init__(self, asr, command_service, tts):
        self.asr, self.command_service, self.tts = asr, command_service, tts

    def handle(self, audio):
        transcript = self.asr.transcribe(audio)
        if not isinstance(transcript,str) or not transcript.strip():
            return {'intent':'unheard','executed':False,'audio':self.tts.synthesize('ขออภัย กรุณาพูดอีกครั้ง')}
        result = self.command_service(transcript)
        if not isinstance(result,dict) or not isinstance(result.get('reply'),str):
            raise ValueError('invalid command response')
        return {**result, 'audio':self.tts.synthesize(result['reply'])}
