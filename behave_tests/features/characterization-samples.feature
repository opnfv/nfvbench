@characterization
Feature: characterization

  @throughput
  Scenario Outline: Run a NDR test for a defined frame size and flow count
      Given 10 sec run duration
      And <frame_size> frame size
      And <flow_count> flow count
      And ndr rate
      When NFVbench API is ready
      Then 3 runs are started and waiting for maximum result
      And push result to database
      And extract offered rate result

     Examples: Frame sizes and flow counts
      | frame_size | flow_count |
      | 64         | 100k        |
      | 768        | 100k        |
      | 1518       | 100k        |
      | 9000       | 100k        |


  @latency
  Scenario Outline: Run a latency test for a defined frame size and throughput percentage
      Given 10 sec run duration
      And <frame_size> frame size
      And 100k flow count
      And <throughput> rate of previous scenario
      When NFVbench API is ready
      Then run is started and waiting for result
      And push result to database

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
