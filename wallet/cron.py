from .views import *

from django.http import HttpRequest

def make_fake_request():
    # Create a fake request object (replace with actual request details)

    request = HttpRequest()
    request.method = 'GET'
    # Set other request attributes as needed
    return request

def my_scheduled_job():

    request = make_fake_request()
    # Call your view function with the request
    print('Cron job running at line no 16')
    res=goal_contribution_alert(request)
    print('Line no 17 cron job response is:',res)



