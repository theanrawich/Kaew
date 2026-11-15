import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from notifications import NoRedirect
from hydration_ai import (recommend, InvalidInput, TransformersProvider, ADVICE_SCHEMA,
                          ChatProvider, select_provider)


class HydrationAITest(unittest.TestCase):
    def setUp(self):
        self.context={'goal_ml':2000,'drank_ml':600,'minutes_since_drink':90,'cup_ml':None,'profile':'balanced'}
        self.output={'next_reminder_minutes':45,'suggested_ml':180,'reason':'Recent intake.'}

    def test_model_result_is_bounded_and_explained(self):
        result=recommend(self.context,lambda c:self.output)
        self.assertEqual(result['next_reminder_minutes'],45)
        self.assertEqual(result['suggested_ml'],180)
        self.assertFalse(result['fallback']); self.assertFalse(result['actuation_allowed'])

    def test_clamping_is_still_a_model_decision(self):
        for minutes,ml,expected in ((1,900,(15,400)),(999,1,(180,100))):
            result=recommend(self.context,lambda c:dict(self.output,next_reminder_minutes=minutes,suggested_ml=ml))
            self.assertEqual((result['next_reminder_minutes'],result['suggested_ml']),expected)
            self.assertFalse(result['fallback']); self.assertFalse(result['actuation_allowed'])

    def test_bad_json_missing_fields_invalid_types_and_transport_fall_back(self):
        values=['bad JSON','{}',None,{},dict(self.output,suggested_ml=True),
                dict(self.output,next_reminder_minutes=float('nan')),dict(self.output,reason=''),
                dict(self.output,actuation_allowed=True)]
        for value in values:
            with self.subTest(value=value):
                result=recommend(self.context,lambda c:value)
                self.assertTrue(result['fallback']); self.assertEqual(result['next_reminder_minutes'],60)
                self.assertEqual(result['suggested_ml'],200); self.assertFalse(result['actuation_allowed'])
        for error in (TimeoutError(),OSError(),ValueError(),HTTPError('https://example.invalid',503,'unavailable',{},None)):
            def failed(c): raise error
            self.assertTrue(recommend(self.context,failed)['fallback'])

    def test_missing_provider_is_offline_fallback(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertIsNone(select_provider())
        result=recommend(self.context,None)
        self.assertTrue(result['fallback']); self.assertIsNone(result['model'])
        self.assertFalse(result['actuation_allowed'])

    def test_invalid_sensor_data_rejected(self):
        with self.assertRaises(InvalidInput): recommend(dict(self.context,cup_ml=float('nan')),None)

    def test_local_provider_accepts_new_contract_and_fences(self):
        provider=TransformersProvider('unused',engine=lambda p:'```json\n'+json.dumps(self.output)+'\n```')
        result=recommend(self.context,provider)
        self.assertFalse(result['fallback']); self.assertFalse(result['actuation_allowed'])

    def test_schema_requires_exact_fields(self):
        self.assertFalse(ADVICE_SCHEMA['additionalProperties'])
        self.assertEqual(set(ADVICE_SCHEMA['required']),set(self.output))

    def test_chat_transport_json_timeout_user_agent_and_no_redirect(self):
        response=MagicMock()
        response.read.return_value=json.dumps({'choices':[{'message':{'content':'```json\n'+json.dumps(self.output)+'\n```'}}]}).encode()
        opener=MagicMock(); opener.open.return_value.__enter__.return_value=response
        with patch('hydration_ai.urllib.request.build_opener',return_value=opener) as build:
            result=recommend(self.context,ChatProvider('groq','test-placeholder'))
        self.assertFalse(result['fallback']); self.assertEqual(result['model'],'openai/gpt-oss-20b')
        self.assertIsInstance(build.call_args.args[0],NoRedirect)
        request=opener.open.call_args.args[0]
        self.assertEqual(opener.open.call_args.kwargs['timeout'],9)
        self.assertEqual(request.get_header('User-agent'),'KaewCloud/0.1')
        self.assertEqual(json.loads(request.data)['response_format'],{'type':'json_object'})
        self.assertEqual(request.full_url,'https://api.groq.com/openai/v1/chat/completions')

    def test_selection_precedence_and_secondary_provider(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':'test-placeholder','OPENROUTER_API_KEY':'test-placeholder','KAEW_OLLAMA_MODEL':'local'},clear=True):
            provider=select_provider()
        first,second=provider.providers
        self.assertEqual(first.model,'openai/gpt-oss-20b')
        self.assertEqual(second.model,'openai/gpt-oss-20b')
        with patch.object(ChatProvider,'__call__',side_effect=[OSError(),self.output]):
            result=recommend(self.context,provider)
        self.assertFalse(result['fallback']); self.assertEqual(result['model'],second.model)
        with patch.dict(os.environ,{'OPENROUTER_API_KEY':'test-placeholder'},clear=True):
            self.assertIn('openrouter.ai',select_provider().url)
        with patch.dict(os.environ,{'KAEW_OLLAMA_MODEL':'local'},clear=True):
            self.assertEqual(select_provider().model,'local')


if __name__=='__main__': unittest.main()
