# from django.test import TestCase, Client
# from django.urls import reverse
# import json
# from .models import *

# class ContributionTestCase(TestCase):
#     def setUp(self):
#         self.client = Client()
#         self.chama = Chama.objects.create(name='Test Chama')
#         self.contribution_data = {
#             'name': 'Test Contribution',
#             'amount': '100.00',
#             'cycle': '30',
#             'start-date': '2024-02-12',
#             'grace-period': '5',
#             'description': 'Test Description',
#         }

#     def test_create_contribution(self):
#         url = reverse('create_contribution', kwargs={'chama_id': self.chama.id})
#         response = self.client.post(url, self.contribution_data, content_type='application/json')
#         self.assertEqual(response.status_code, 200)
#         data = json.loads(response.content)
#         self.assertEqual(data['status'], 'success')
#         self.assertEqual(Contribution.objects.filter(chama=self.chama).count(), 1)

#     def test_create_contribution_record(self):
#         contribution = Contribution.objects.create(name='Test Contribution', amount='100.00', cycle_days=30,
#                                                    start_date='2024-02-12', grace_period=5, description='Test Desc',
#                                                    chama=self.chama)
#         member = ChamaMember.objects.create(name='Test Member')
#         contribution_data = {
#             'contribution': contribution.id,
#             'amount': '50.00',
#             'member': member.id,
#         }
#         url = reverse('create_contribution_record', kwargs={'chama_id': self.chama.id})
#         response = self.client.post(url, json.dumps(contribution_data), content_type='application/json')
#         self.assertEqual(response.status_code, 200)
#         data = json.loads(response.content)
#         self.assertEqual(data['status'], 'success')
#         self.assertEqual(ContributionRecord.objects.count(), 1)
#         self.assertEqual(ContributionRecord.objects.first().contribution, contribution)


# # Make sure to add more test cases to cover edge cases and error scenarios.
