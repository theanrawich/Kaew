import unittest
from asr_eval import edit_distance, evaluate_cases
from voice import parse_text


class EvalTest(unittest.TestCase):
    def test_edit_distance_and_weighted_rates(self):
        self.assertEqual(edit_distance(list('abc'),list('adc')),1)
        cases=[{'text':'แก้ว เติมน้ำให้หน่อย','intent':'refill','audio':'a'},
               {'text':'แก้ว ตอนนี้น้ำเหลือเท่าไหร่','intent':'level','audio':'b'}]
        predictions={'a':'แก้ว เติมน้ำให้หน่อย','b':'แก้ว ตอนนี้น้ำเหลือเท่าไหร่'}
        result=evaluate_cases(cases,lambda p:predictions[p],lambda s:s.split())
        self.assertEqual(result['cer'],0); self.assertEqual(result['wer'],0); self.assertEqual(result['intent_accuracy'],1)

    def test_wrong_or_failed_recognition_is_not_counted_correct(self):
        cases=[{'text':'แก้ว เติมน้ำให้หน่อย','intent':'refill','audio':'a'}]
        result=evaluate_cases(cases,lambda p:'',lambda s:s.split())
        self.assertEqual(result['intent_accuracy'],0); self.assertGreater(result['cer'],0)

    def test_thai_spoken_numbers_are_normalized_for_error_rates(self):
        cases=[{'text':'แก้ว เตือนอีก 30 นาที','intent':'reminder','audio':'a'}]
        result=evaluate_cases(cases,lambda p:'แก้ว เตือนอีก สามสิบ นาที',lambda s:s.split())
        self.assertEqual(result['cer'],0); self.assertEqual(result['wer'],0)
        self.assertEqual(result['intent_accuracy'],1)

    def test_malformed_spoken_number_requires_clarification(self):
        self.assertEqual(parse_text('แก้ว เตือนอีก สิบสิบ นาที')['intent'],'clarify_reminder')

    def test_wake_recall_and_false_activation_are_separate_from_intent(self):
        cases=[{'text':'แก้ว เติมน้ำให้หน่อย','intent':'refill','audio':'a'},
               {'text':'พูดเรื่องอื่น','intent':'no_wake','audio':'b'}]
        responses={'a':'แก้ว เติมน้ำให้หน่อย','b':'แก้ว เติมน้ำให้หน่อย'}
        result=evaluate_cases(cases,lambda p:responses[p],lambda s:s.split())
        self.assertEqual(result['wake_recall'],1)
        self.assertEqual(result['false_activation_rate'],1)

if __name__=='__main__': unittest.main()
