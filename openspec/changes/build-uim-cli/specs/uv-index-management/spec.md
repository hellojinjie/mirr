## Purpose

Provide an nrm-shaped command-line workflow for safely managing uv package indexes at user and project scope without discarding unrelated uv configuration.

## ADDED Requirements

### Requirement: Installable uim command
The project SHALL provide a `uim` command that runs on supported CPython versions 3.9 and later and exposes help and version output without requiring a project environment.

#### Scenario: Invoke the installed command
- **WHEN** a user installs the package and runs `uim --help`
- **THEN** the command displays its available commands and exits successfully

#### Scenario: Display the version
- **WHEN** a user runs `uim --version`
- **THEN** the command displays the installed uim version and exits successfully

### Requirement: nrm-compatible core command surface
The CLI SHALL provide `ls`, `current`, `use`, `add`, `del`, `rename`, `home`, and `test` commands with positional argument shapes and commonly used options matching nrm wherever uv has equivalent behavior.

#### Scenario: Discover familiar commands
- **WHEN** an nrm user runs `uim --help`
- **THEN** the help lists the core commands using their nrm names

#### Scenario: Request command-specific help
- **WHEN** a user runs `uim <command> --help` for a core command
- **THEN** the command displays its arguments and options and exits successfully

### Requirement: Built-in index catalog
The system SHALL provide built-in entries for PyPI, Tsinghua, Aliyun, Tencent, Huawei, and USTC using HTTPS PEP 503 Simple Repository endpoints.

#### Scenario: List a fresh installation
- **WHEN** a user with no uim catalog configuration runs `uim ls`
- **THEN** all built-in entries are listed with their names and URLs

#### Scenario: Protect a built-in entry
- **WHEN** a user attempts to delete or rename a built-in entry
- **THEN** uim rejects the operation, leaves the catalog unchanged, and returns a non-zero exit status

### Requirement: Custom index catalog management
The system SHALL let users add, delete, and rename custom index entries, with an optional homepage, in a platform-appropriate per-user uim configuration file.

#### Scenario: Add a custom index
- **WHEN** a user runs `uim add company https://packages.example.com/simple https://packages.example.com`
- **THEN** uim validates and stores the custom entry and makes it available to subsequent commands

#### Scenario: Reject an invalid custom index
- **WHEN** an add or rename operation supplies an invalid URL, invalid name, or duplicate destination name
- **THEN** uim reports the validation error, makes no catalog change, and returns a non-zero exit status

#### Scenario: Delete a custom index
- **WHEN** a user runs `uim del company` for an existing custom entry that is not currently selected in a managed scope
- **THEN** uim removes that entry from the catalog

#### Scenario: Protect an active custom index
- **WHEN** a user attempts to delete a custom entry currently selected by a uim-managed configuration
- **THEN** uim rejects the deletion and explains that another index must be selected first

### Requirement: User-level index switching
The `uim use <name>` command SHALL set the selected catalog URL as uv's user-level default index while preserving unrelated settings and indexes in the same configuration file.

#### Scenario: Switch the user default
- **WHEN** a user runs `uim use tsinghua` and no unsafe configuration conflict exists
- **THEN** the uv user configuration uses the Tsinghua URL as its default index and uim reports success

#### Scenario: Select an unknown entry
- **WHEN** a user runs `uim use missing` and `missing` is not in the catalog
- **THEN** uim reports that the entry is unknown, makes no configuration change, and returns a non-zero exit status

#### Scenario: Choose interactively
- **WHEN** a user runs `uim use` in an interactive terminal without a name
- **THEN** uim prompts the user to select from the catalog and applies the selected user-level index

#### Scenario: Omit a name in non-interactive use
- **WHEN** a user runs `uim use` without a name and standard input is not interactive
- **THEN** uim reports that a name is required, makes no configuration change, and returns a non-zero exit status

### Requirement: Project-level index switching
The `uim use <name> --local` command SHALL set the selected index for the current uv project without altering the user-level uv configuration.

#### Scenario: Update an existing local uv.toml
- **WHEN** the current project resolves to an existing `uv.toml` and a user runs `uim use aliyun --local`
- **THEN** uim updates that file's default index and leaves the user configuration unchanged

#### Scenario: Update an existing pyproject.toml
- **WHEN** no applicable `uv.toml` exists, an applicable `pyproject.toml` exists, and a user runs `uim use aliyun --local`
- **THEN** uim updates the `[tool.uv]` configuration in that `pyproject.toml` and leaves the user configuration unchanged

#### Scenario: Create local configuration outside an existing project
- **WHEN** neither an applicable `uv.toml` nor `pyproject.toml` exists and a user confirms a local switch
- **THEN** uim creates `uv.toml` in the current directory containing the selected default index

### Requirement: Configuration preservation and atomicity
Every switch SHALL preserve comments, formatting where practical, and all uv settings not directly superseded by the requested default-index change, and SHALL replace the target file atomically.

#### Scenario: Preserve unrelated configuration
- **WHEN** a target configuration contains unrelated settings, named supplemental indexes, and comments
- **THEN** switching the default index retains those settings, indexes, and comments

#### Scenario: Abort a failed write
- **WHEN** validation or filesystem replacement fails during a switch
- **THEN** the original target file remains usable and uim returns a non-zero exit status

#### Scenario: Encounter an unmanaged structured default
- **WHEN** the target contains an unmanaged `[[index]]` entry marked `default = true` whose extra attributes cannot be safely represented by a simple default-index switch
- **THEN** uim reports the conflict and makes no change unless the user explicitly requests an approved override mode

### Requirement: Effective current index reporting
The `uim current` command SHALL determine the effective default index for the current directory using uv's environment, project, user, and system precedence, and SHALL identify a matching catalog name when possible.

#### Scenario: Project index overrides user index
- **WHEN** the current project selects Aliyun and the user configuration selects PyPI
- **THEN** `uim current` reports `aliyun`

#### Scenario: Show the effective URL
- **WHEN** a user runs `uim current --show-url` or `uim current -u`
- **THEN** uim displays the effective default index URL instead of its catalog name

#### Scenario: Environment override is active
- **WHEN** a supported uv default-index environment variable overrides persistent configuration
- **THEN** `uim current` reports the environment-selected index and verbose output identifies the environment as its source

#### Scenario: Effective URL is not cataloged
- **WHEN** the effective default URL does not match any catalog entry
- **THEN** `uim current` displays the URL rather than inventing a name

### Requirement: Registry list identifies the effective selection
The `uim ls` command SHALL display all catalog entries and mark the entry matching the effective default index for the current directory.

#### Scenario: Mark a selected entry
- **WHEN** the effective index matches a catalog entry and a user runs `uim ls`
- **THEN** exactly that entry is marked as current

#### Scenario: No catalog entry matches
- **WHEN** the effective index is not present in the catalog and a user runs `uim ls`
- **THEN** the catalog is listed without falsely marking an entry and the effective custom URL is clearly reported

### Requirement: Index homepage access
The `uim home <name> [browser]` command SHALL open the configured homepage for an index using the requested browser when supplied or the platform default otherwise.

#### Scenario: Open a configured homepage
- **WHEN** a user invokes `uim home pypi` in an interactive desktop environment
- **THEN** uim requests that the platform open PyPI's configured homepage

#### Scenario: Homepage is unavailable
- **WHEN** an index has no homepage or the requested browser cannot be launched
- **THEN** uim reports the problem and returns a non-zero exit status

### Requirement: Index reachability testing
The `uim test [name]` command SHALL measure HTTPS reachability and response latency for one named index or all catalog entries without modifying configuration or downloading a Simple Repository root index. It SHALL probe a lightweight project endpoint beneath the configured Simple Repository URL, prefer a bodyless `HEAD` request, and only fall back to a byte-bounded `GET` when the server explicitly does not support `HEAD`.

#### Scenario: Test one index
- **WHEN** a user runs `uim test tsinghua`
- **THEN** uim reports whether a lightweight project endpoint beneath its Simple Repository URL responded successfully and includes elapsed time on success

#### Scenario: Test all indexes
- **WHEN** a user runs `uim test` without a name
- **THEN** uim tests catalog entries concurrently, reports an individual result for each, and does not change the selected index

#### Scenario: Avoid downloading the root index
- **WHEN** uim tests an index whose Simple Repository root contains a large project listing
- **THEN** uim does not issue a `GET` for the root index and does not consume an unbounded response body

#### Scenario: Server does not support HEAD
- **WHEN** the lightweight project endpoint returns HTTP 405 or 501 to a `HEAD` request
- **THEN** uim retries that same project endpoint with `Range: bytes=0-0` and reads no more than one response byte

#### Scenario: Endpoint fails
- **WHEN** an endpoint times out, fails TLS validation, or returns an unacceptable response
- **THEN** uim reports a failure for that entry without exposing credentials embedded in an input URL

### Requirement: Secret-safe behavior
The system SHALL NOT persist credentials in the uim catalog, echo URL credentials in normal output, or implement a separate credential store in the initial release.

#### Scenario: URL contains credentials
- **WHEN** a user attempts to add an index URL containing user information
- **THEN** uim rejects the URL and directs the user toward uv-supported authentication

#### Scenario: Diagnostic error includes a sensitive URL
- **WHEN** an HTTP or parsing error references a URL containing sensitive user information
- **THEN** uim redacts the sensitive portion before displaying the error
