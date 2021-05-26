@quick-test-10kpps
Feature: quick-test-10kpps

  @throughput
  Scenario: Run a 10s test at 10kpps with 64-byte frames and 128 flows
      Given 10 sec run duration
      And TRex is restarted
      And 64 frame size
      And 128 flow count
      And 10kpps rate
      When NFVbench API is ready
      Then 1 runs are started and waiting for maximum result
      And push result to database
