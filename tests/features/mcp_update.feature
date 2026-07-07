Feature: Living update when a new trial lands
  The living layer's promise: an existing review, re-run against one more trial,
  reports the new pooled estimate and flags whether the conclusion changed — all
  driven through the MCP `update` tool.

  Scenario: A new trial is added to an existing review
    Given a saved review of the first seven GLP-1 MACE trials
    When the eighth trial lands via the update tool
    Then the diff reports eight pooled trials
    And the diff lists the newly added trial
    And the diff states whether the conclusion changed
