"""
Project structure validation tests.

Verifies the expected directory structure and key files exist.
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestProjectStructure:
    """Test project directory structure."""

    def test_scripts_directory_structure(self):
        """Scripts should be organized into subdirectories."""
        scripts_dir = os.path.join(PROJECT_ROOT, "scripts")
        expected_dirs = ["examples", "quickstarts", "tools", "connectivity", "testdata"]

        for subdir in expected_dirs:
            path = os.path.join(scripts_dir, subdir)
            assert os.path.isdir(path), f"Missing scripts/{subdir}/"

    def test_examples_directory_has_tutorials(self):
        """Examples directory should contain tutorial scripts."""
        examples_dir = os.path.join(PROJECT_ROOT, "scripts", "examples")
        expected_files = [
            "01-basics.py",
            "02-transformations.py",
            "03-streaming-basic.py",
            "04-kafka-streaming.py",
        ]

        for filename in expected_files:
            path = os.path.join(examples_dir, filename)
            assert os.path.isfile(path), f"Missing scripts/examples/{filename}"

    def test_tools_directory_has_utilities(self):
        """Tools directory should contain utility scripts."""
        tools_dir = os.path.join(PROJECT_ROOT, "scripts", "tools")
        expected_files = ["download-jars.sh", "kafka-producer.py"]

        for filename in expected_files:
            path = os.path.join(tools_dir, filename)
            assert os.path.isfile(path), f"Missing scripts/tools/{filename}"

    def test_connectivity_directory_has_tests(self):
        """Connectivity directory should contain test scripts."""
        conn_dir = os.path.join(PROJECT_ROOT, "scripts", "connectivity")
        expected_files = ["test-iceberg.py", "test-kafka.py"]

        for filename in expected_files:
            path = os.path.join(conn_dir, filename)
            assert os.path.isfile(path), f"Missing scripts/connectivity/{filename}"

    def test_quickstarts_directory_has_demos(self):
        """Quickstarts directory should contain demo scripts."""
        qs_dir = os.path.join(PROJECT_ROOT, "scripts", "quickstarts")
        expected_files = ["iceberg-spark-quickstart.py", "lance-quickstart.py"]

        for filename in expected_files:
            path = os.path.join(qs_dir, filename)
            assert os.path.isfile(path), f"Missing scripts/quickstarts/{filename}"


class TestKeyFiles:
    """Test key project files exist."""

    def test_cli_script_exists(self):
        """Lakehouse CLI should exist and be executable."""
        cli_path = os.path.join(PROJECT_ROOT, "lakehouse")
        assert os.path.isfile(cli_path), "Missing lakehouse CLI"

    def test_docker_compose_files_exist(self):
        """Docker compose files should exist."""
        compose_files = [
            "docker-compose.yml",
            "docker-compose-spark41.yml",
            "docker-compose-kafka.yml",
        ]

        for filename in compose_files:
            path = os.path.join(PROJECT_ROOT, filename)
            assert os.path.isfile(path), f"Missing {filename}"

    def test_env_example_exists(self):
        """Environment example file should exist."""
        env_path = os.path.join(PROJECT_ROOT, ".env.example")
        assert os.path.isfile(env_path), "Missing .env.example"

    def test_documentation_exists(self):
        """Key documentation files should exist."""
        docs = [
            "README.md",
            "CLAUDE.md",
            "docs/README.md",
            "docs/architecture.md",
            "docs/troubleshooting.md",
        ]

        for doc in docs:
            path = os.path.join(PROJECT_ROOT, doc)
            assert os.path.isfile(path), f"Missing {doc}"


class TestTestdataModule:
    """Test testdata module structure."""

    def test_testdata_is_package(self):
        """Testdata should be a proper Python package."""
        testdata_dir = os.path.join(PROJECT_ROOT, "scripts", "testdata")
        init_file = os.path.join(testdata_dir, "__init__.py")
        assert os.path.isfile(init_file), "Missing scripts/testdata/__init__.py"

    def test_testdata_has_main(self):
        """Testdata should have __main__.py for CLI execution."""
        testdata_dir = os.path.join(PROJECT_ROOT, "scripts", "testdata")
        main_file = os.path.join(testdata_dir, "__main__.py")
        assert os.path.isfile(main_file), "Missing scripts/testdata/__main__.py"

    def test_testdata_modules_exist(self):
        """Testdata should have all required modules."""
        testdata_dir = os.path.join(PROJECT_ROOT, "scripts", "testdata")
        modules = ["config.py", "dimensions.py", "events.py", "producer.py", "exporter.py"]

        for module in modules:
            path = os.path.join(testdata_dir, module)
            assert os.path.isfile(path), f"Missing scripts/testdata/{module}"
