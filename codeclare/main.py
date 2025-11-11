import argparse
import json
import os
import subprocess
from pathlib import Path
from .parser import load_spec
from .contract_builder import build_contract
from .tlsf_exporter import export_tlsf
from .utils.strategy_utils import dot_to_pdf, display_pdf_in_colab


def run_lydia_synthesis(tlsf_path: Path, output_dir: Path) -> Path:
    """
    Run LydiaSyft inside Docker container `lydiasyft_dev`
    using the syntax: ./bin/LydiaSyft -p synthesis -f <file>.
    Captures realizability result and copies strategy.dot back to host.
    """
    tlsf_abs = tlsf_path.resolve()
    out_abs = output_dir.resolve()
    strategy_path = out_abs / "strategy.dot"

    container_name = "lydiasyft_dev"
    container_outputs = "/LydiaSyft/outputs"
    container_tlsf = f"{container_outputs}/{tlsf_abs.name}"
    container_strategy = "/LydiaSyft/build/strategy.dot"

    # Ensure container is running
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
        capture_output=True, text=True
    )
    if "true" not in result.stdout:
        subprocess.run(["docker", "start", container_name], check=True)

    # Ensure outputs directory
    subprocess.run(["docker", "exec", container_name, "mkdir", "-p", container_outputs], check=True)

    # Copy TLSF file to container (suppressing copy logs)
    subprocess.run(
        ["docker", "cp", str(tlsf_abs), f"{container_name}:{container_tlsf}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )

    # Run LydiaSyft inside container
    cmd = [
        "docker", "exec", container_name,
        "bash", "-c",
        f"cd /LydiaSyft/build && ./bin/LydiaSyft -p synthesis -f {container_tlsf}"
    ]
    try:
        # Keep LydiaSyft’s output (it prints REALIZABLE/UNREALIZABLE)
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"LydiaSyft synthesis failed (exit code {e.returncode}).")
        raise

    # Copy strategy.dot back
    subprocess.run(
        ["docker", "cp", f"{container_name}:{container_strategy}", str(strategy_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )

    if not strategy_path.exists():
        raise FileNotFoundError("No strategy .dot file produced by LydiaSyft.")

    return strategy_path


def main():
    ap = argparse.ArgumentParser(description="coDECLARE → LTLf → TLSF → LydiaSyft")
    ap.add_argument("--in", dest="input_path", required=True, help="Input coDECLARE JSON file")
    args = ap.parse_args()

    input_path = Path(args.input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    print(f"Loading coDECLARE model from {input_path}")
    spec = load_spec(input_path)

    # Step 1: Build assume–guarantee contract
    print("Building assume-guarantee LTLf contract...")
    result = build_contract(spec)

    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    base = input_path.stem

    ltlf_out = outputs_dir / f"{base}.ltlf"
    tlsf_out = outputs_dir / f"{base}.tlsf"

    # Step 2: Save .ltlf and .tlsf
    ltlf_out.write_text(result["contract_ltlf"])
    export_tlsf(result, tlsf_out, title=f"coDECLARE contract ({base})")

    print(f"\nContract files generated:")
    print(f"  LTLf:  {ltlf_out}")
    print(f"  TLSF:  {tlsf_out}")

    # Step 3: Run LydiaSyft synthesis
    try:
        strategy_dot = run_lydia_synthesis(tlsf_out, outputs_dir)

        # Step 4: Convert to PDF
        pdf_path = dot_to_pdf(strategy_dot)

        # Step 5: Display in Colab (optional)
        if "COLAB_RELEASE_TAG" in os.environ:
            display_pdf_in_colab(str(pdf_path))

    except subprocess.CalledProcessError as e:
        print(f"LydiaSyft synthesis failed with error code {e.returncode}")
    except Exception as e:
        print(e)

    print("Pipeline completed.")


if __name__ == "__main__":
    main()
