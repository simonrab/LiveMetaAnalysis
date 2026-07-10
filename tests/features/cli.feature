Feature: Command-line meta-analysis over the shared core
  A reviewer drives the whole workflow from the terminal, fully offline, and the
  CLI reports honestly what it found and what it could not — the same shared core
  the web app and MCP server use, reached through the `livemeta` command.

  Scenario: Run the locked demo and read the report with a forest plot
    Given ClinicalTrials.gov results are served from recorded fixtures
    When I run the demo review from the command line
    Then the pooled hazard ratio in the report rounds to 0.86
    And the terminal report includes an ASCII forest plot with a pooled row
    And the review is saved as version 1

  Scenario: Inject a new trial and see the conclusion diff
    Given a saved command-line review of the first seven GLP-1 MACE trials
    When I add the eighth trial from the command line
    Then the diff report shows eight pooled trials
    And the diff report states whether the conclusion changed

  Scenario: Flag a trial from the command line and re-pool
    Given a saved command-line review of the eight GLP-1 MACE trials
    When I flag the first trial from the command line
    Then the re-pooled report includes seven trials
    And the decision is saved to the audit trail

  Scenario: Honest behaviour with no model key
    Given ClinicalTrials.gov results are served from recorded fixtures
    When I run the demo review from the command line
    Then the report marks risk of bias as PENDING rather than fabricating it
