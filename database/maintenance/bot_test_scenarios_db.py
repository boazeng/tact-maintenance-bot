"""
bot_test_scenarios_db — storage dispatcher for saved bot-test scenarios.

Test scenarios are a development/QA artifact, so they live in the local SQLite
backend regardless of STORAGE_BACKEND (there is no production DynamoDB table for
them). Public API: get_scenario, save_scenario, list_scenarios, delete_scenario.
"""

from database.backends.sqlite import test_scenarios as _impl

get_scenario = _impl.get_scenario
save_scenario = _impl.save_scenario
list_scenarios = _impl.list_scenarios
delete_scenario = _impl.delete_scenario
