Feature: Appraisal and sensitivity round out the pooled answer
  A credible meta-analysis appraises its trials and probes its own robustness.
  After pooling, the pipeline assesses risk of bias per trial, runs a
  leave-one-out sensitivity check, and rates GRADE certainty — and a reviewer can
  sign off a RoB domain, which persists to the audit trail.

  Scenario: A pooled review is appraised and a RoB domain is confirmed
    Given a pooled review of the eight GLP-1 MACE trials
    Then every pooled trial has a risk-of-bias assessment
    And a leave-one-out row is produced for each trial
    And the review carries a GRADE certainty rating
    When a reviewer confirms a risk-of-bias domain on the first trial
    Then that domain is marked confirmed in the audit trail
