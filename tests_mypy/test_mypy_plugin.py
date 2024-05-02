from mypy import api
import os


EXPECT_LINE = "# expect: "
EXPECT_LINE_OUTPUT = "Revealed type is "


def test_file(directory: str, file_name: str) -> bool:
    expected: list[str] = []
    file_path = os.path.join(directory, file_name)
    with open(file_path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith(EXPECT_LINE):
                expected.append(line[len(EXPECT_LINE):].strip())

    result = api.run([
        "--config-file=../mypy_plugin.ini",
        "--show-traceback",
        file_path])

    output_expected: list[str] = []
    for output_line in result[0].splitlines():
        index = output_line.find(EXPECT_LINE_OUTPUT)
        if index > 0:
            output_expected.append(output_line[index + len(EXPECT_LINE_OUTPUT):].strip().strip('"'))

    if expected == output_expected:
        print(f"PASS {file_name}")
        return True
    else:
        print(f"FAIL {file_name}\n")
        print(f"Expected: {repr(expected)}")
        print(f"Received: {repr(output_expected)}")
        print("STDOUT----------------")
        print(result[0])
        print(result[1])
        print("----------------------")
        return False

def main() -> None:
    directory = '.'
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and f.startswith("case_")]
    files.sort()

    for file_name in files:
        test_file(directory, file_name)

main()
