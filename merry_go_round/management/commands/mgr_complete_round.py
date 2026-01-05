
def handle(self, *args, **options):
    """Simulate a full round from start to finish"""
    round_id = options['round_id']
    # Fast-forward and simulate each cycle automatically