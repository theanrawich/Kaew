import unittest
from hydration_ai import recommend, InvalidInput, TransformersProvider, ADVICE_SCHEMA


class HydrationAITest(unittest.TestCase):
    def setUp(self):
        self.context={'goal_ml':2000,'drank_ml':600,'minutes_since_drink':90,'cup_ml':20,'profile':'balanced'}

    def test_model_result_is_bounded_and_explained(self):
        model=lambda context: {'refill_ml':180,'reminder_minutes':45,'confidence':0.8,'explanation':'Recent intake is low.'}
        result=recommend(self.context,model)
        self.assertEqual(result['source'],'model'); self.assertEqual(result['refill_ml'],180)
        self.assertIn('explanation',result)

    def test_invalid_low_confidence_or_failed_model_falls_back(self):
        for value in ({'refill_ml':1000,'reminder_minutes':1,'confidence':1,'explanation':'unsafe'},
                      {'refill_ml':180,'reminder_minutes':45,'confidence':0.1,'explanation':'uncertain'},None):
            result=recommend(self.context,lambda c:value)
            self.assertEqual(result['source'],'fallback'); self.assertLessEqual(result['refill_ml'],250)
        def failed(c): raise OSError('offline')
        self.assertEqual(recommend(self.context,failed)['source'],'fallback')

    def test_invalid_sensor_data_rejected(self):
        with self.assertRaises(InvalidInput): recommend(dict(self.context,cup_ml=float('nan')),None)

    def test_missing_cup_data_cannot_suggest_dispensing_volume(self):
        model=lambda context: {'refill_ml':200,'reminder_minutes':45,'confidence':0.8,'explanation':'ok'}
        result=recommend(dict(self.context,cup_ml=None),model)
        self.assertEqual(result['source'],'fallback')
        self.assertEqual(result['refill_ml'],0)
        self.assertFalse(result['actuation_allowed'])

    def test_local_provider_validates_json_and_never_authorizes_actuation(self):
        provider=TransformersProvider('unused',engine=lambda prompt: '{"refill_ml":150,"reminder_minutes":45,"confidence":0.8,"explanation":"Recent intake."}')
        result=recommend(self.context,provider)
        self.assertEqual(result['source'],'model')
        self.assertFalse(result['actuation_allowed'])
        self.assertEqual(recommend(self.context,TransformersProvider('unused',engine=lambda p: 'not JSON'))['source'],'fallback')

    def test_schema_requires_exact_advisory_fields(self):
        self.assertFalse(ADVICE_SCHEMA['additionalProperties'])
        self.assertEqual(set(ADVICE_SCHEMA['required']),{'refill_ml','reminder_minutes','confidence','explanation'})


if __name__=='__main__': unittest.main()
