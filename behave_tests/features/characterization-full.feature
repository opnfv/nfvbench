@characterization
Feature: characterization

  @throughput
  Scenario Outline: Run a NDR test for a defined frame size and flow count
      Given 10 sec run duration
      And TRex is restarted
      And <frame_size> frame size
      And <flow_count> flow count
      And ndr rate
      When NFVbench API is ready
      Then 3 runs are started and waiting for maximum result
      And push result to database
      And extract offered rate result

     Examples: Frame sizes and flow counts
      | frame_size | flow_count |
      | 64         | 128        |
      | 128        | 128        |
      | 256        | 128        |
      | 512        | 128        |
      | 768        | 128        |
      | 1024       | 128        |
      | 1280       | 128        |
      | 1518       | 128        |
      | IMIX       | 128        |
      | 9000       | 128        |
      | 64         | 10k        |
      | 128        | 10k        |
      | 256        | 10k        |
      | 512        | 10k        |
      | 768        | 10k        |
      | 1024       | 10k        |
      | 1280       | 10k        |
      | 1518       | 10k        |
      | IMIX       | 10k        |
      | 9000       | 10k        |
      | 64         | 100k       |
      | 128        | 100k       |
      | 256        | 100k       |
      | 512        | 100k       |
      | 768        | 100k       |
      | 1024       | 100k       |
      | 1280       | 100k       |
      | 1518       | 100k       |
      | IMIX       | 100k       |
      | 9000       | 100k       |


  @latency
  Scenario Outline: Run a latency test for a defined frame size and throughput percentage
      Given 10 sec run duration
      And TRex is restarted
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
