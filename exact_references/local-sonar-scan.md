# Running SonarQube / SonarCloud locally

Supporting detail for [resolve-sonarqube-issues](../skills/resolve-sonarqube-issues/SKILL.md). Use this for running `sonar-scanner` on a local machine, covering prerequisites by language, monorepo patterns, and environment setup.

## Prerequisites

- `sonar-scanner` installed (e.g., `brew install sonar-scanner` on macOS, or download from the SonarQube docs)
- `SONAR_TOKEN` set in the environment, or `sonar.token` set in the properties file (obtain from your SonarQube / SonarCloud account settings)
- `sonar.host.url` set to your server URL — typically in the properties file. `sonar-scanner` defaults to `http://localhost:9000` when unset, not sonarcloud.io

## Project configuration

`sonar-scanner` reads configuration from `sonar-project.properties` in the working directory. Always read this file first to obtain the project key, organization, source paths, and any language-specific settings — do not hardcode these values.

For a second project in the same repo (e.g., a monorepo), a separate properties file is typically provided (e.g., `sonar-project-server.properties`). Pass it with `-Dproject.settings=<file>`.

## Language-specific prerequisites

Run these steps before invoking `sonar-scanner`. Skip any that do not apply to the project.

### Python

Generate a coverage report in Cobertura XML format:

```bash
python3 -m pytest <tests-dir> \
  --cov=<source-dir> \
  --cov-report=xml:<output-path>.xml
```

The output path must match the value of `sonar.python.coverage.reportPaths` in the properties file.

### Swift / CFamily (macOS only)

Swift and C/C++ analysis requires the Sonar build-wrapper to capture compiler invocations and `xccov` for coverage.

**1. Download build-wrapper** (cache it to avoid re-downloading):

```bash
BW_CACHE="/tmp/sonar-build-wrapper"
if [[ ! -f "$BW_CACHE/build-wrapper-macos-x86" ]]; then
  TMP_ZIP=$(mktemp /tmp/build-wrapper-XXXXXX.zip)
  curl -sSLo "$TMP_ZIP" "${SONAR_HOST_URL:-https://sonarcloud.io}/static/cpp/build-wrapper-macos-x86.zip"
  mkdir -p "$BW_CACHE"
  unzip -qj "$TMP_ZIP" "build-wrapper-macos-x86/build-wrapper-macos-x86" -d "$BW_CACHE"
  rm "$TMP_ZIP"
fi
```

**2. Build and test wrapped with build-wrapper:**

```bash
"$BW_CACHE/build-wrapper-macos-x86" --out-dir bw-output \
  xcodebuild test \
    -scheme <SchemeName> \
    -configuration Debug \
    -destination "platform=iOS Simulator,name=<SimulatorName>" \
    -enableCodeCoverage YES \
    -resultBundlePath test.xcresult \
    CODE_SIGN_IDENTITY="" \
    CODE_SIGNING_REQUIRED=NO \
    CODE_SIGNING_ALLOWED=NO
```

To find an available simulator name:

```bash
xcrun simctl list devices available -j \
  | python3 -c "
import json, sys
devices = json.load(sys.stdin)['devices']
for runtime, devs in devices.items():
    if 'iOS' in runtime:
        for d in devs:
            if d.get('isAvailable'):
                print(d['name']); sys.exit(0)
sys.exit(1)"
```

**3. Export coverage:**

```bash
xcrun xccov view --report --json test.xcresult > xccov-report.json
```

The output paths `bw-output` and `xccov-report.json` must match `sonar.cfamily.build-wrapper-output` and `sonar.cfamily.xccov.reportPaths` in the properties file.

### JavaScript / TypeScript

Generate coverage using the test framework configured in the project (e.g., Jest, Vitest). The output format and path must match `sonar.javascript.lcov.reportPaths` or equivalent in the properties file.

### Java / Kotlin

Compile and test the project using Maven or Gradle first. Coverage is typically captured automatically by the SonarQube scanner plugin.

## Running the scan

After completing any language-specific prerequisites:

```bash
# Default properties file (sonar-project.properties)
# sonar.host.url is typically already set in the properties file
sonar-scanner

# Alternate properties file
sonar-scanner -Dproject.settings=sonar-project-server.properties

# If sonar.host.url is not in the properties file, pass it explicitly
sonar-scanner -Dsonar.host.url=https://sonarcloud.io
```

## Monorepos with multiple projects

When a repo contains more than one SonarQube project (e.g., separate projects for server and mobile code), run `sonar-scanner` once per project, each with its own properties file. The scan for each project is independent — results do not overwrite each other.

## Polling for analysis completion

After `sonar-scanner` exits, the server may take a minute or more to publish the results. Use the `project_analyses/search` API to detect when the new analysis appears before reading results. See the polling strategy in [SKILL.md](../skills/resolve-sonarqube-issues/SKILL.md) Phase 2.
