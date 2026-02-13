import bauplan
from bauplan.standard_expectations import expect_column_no_nulls


@bauplan.expectation()
@bauplan.python('3.11')
def test_null_values_timestamp(
        data=bauplan.Model(
            # as input, we declare the bauplan model that we want to check
            'ny_taxi_trips_and_zones',
            columns=['PULocationID'],
        )
):
    """

    As we are calculating the difference between request_datetime and on_scene_datetime
    we want toe make sure that on_scene_datetime has no null values.

    """
    columnn_to_check = 'PULocationID'
    _is_expectation_correct = expect_column_no_nulls(data, columnn_to_check)

    # assert the result of the test. In this way, the pipeline will stop running if the expectation tests fails
    # in this way we can prevent data quality issues to become part of our production environment set up alerts.
    assert _is_expectation_correct, "expectation test failed: we expected on_scene_datetime to have no null values"

    # print the result of the test. In this way, the pipeline will not stop even if the expectation tests fails
    # in case of failure we are simply printing out the result of the test
    # if _is_expectation_correct:
    #     print('\nexpectation test passed with flying colors\n')
    # else:
    #     print('\nexpectation test failed!\n')

    return _is_expectation_correct  # return a boolean


