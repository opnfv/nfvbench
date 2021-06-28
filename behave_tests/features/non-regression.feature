@non-regression
Feature: non-regression

  @throughput
  Scenario Outline: Run a NDR test for a defined frame size
      Given 10 sec run duration
      And <frame_size> frame size
      And 100k flow count
      And ndr rate
      When NFVbench API is ready
      Then 3 runs are started and waiting for maximum result
      And push result to database
      And extract offered rate result
      And verify throughput result is in same range as the previous result
      And verify throughput result is in same range as the characterization result

     Examples: Frame sizes
      | frame_size |
      | 64         |
      | 768        |
      | 1518       |
      | 9000       |


  @latency
  Scenario Outline: Run a latency test for a defined frame size and throughput percentage
      Given 10 sec run duration
      And <frame_size> frame size
      And 100k flow count
      And <throughput> rate of previous scenario
      When NFVbench API is ready
      Then run is started and waiting for result
      And push result to database
      And verify latency result is lower than 1000 microseconds

     Examples: Frame sizes and throughput percentages
      | frame_size | throughput |
      | 64         | 70%        |
      | 64         | 90%        |
      | 768        | 70%        |
      | 768        | 90%        |
      | 1518       | 70%        |
      | 1518       | 90%        |
      | 9000       | 70%        |
      | 9000       | 90%        |
