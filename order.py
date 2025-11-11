from codeclare.models.codeclare_model import CoDeclareModel
from pathlib import Path
import subprocess

# Create the coDECLARE model
model = CoDeclareModel()

# Environment and system activities
for a in ["regaddr", "pay", "reqc", "open"]:
    model.add_environment_activity(a)
for a in ["skip", "ship", "cancel", "refund"]:
    model.add_system_activity(a)

# Add assumptions
model.add_assumption("precedence", ["regaddr", "ship"])
model.add_assumption("responded_existence", ["open", "regaddr"])
model.add_assumption("absence2", ["pay"])

# Add guarantees
model.add_guarantee("neg_succession", ["reqc", "pay"])
model.add_guarantee("response", ["reqc", "cancel", "refund"])
model.add_guarantee("not_coexistence", ["cancel", "refund"])
model.add_guarantee("succession", ["pay", "ship"])

# Save model to input folder
Path("input").mkdir(exist_ok=True)
model_path = Path("input/order_demo.json")
model.to_json(str(model_path))

# Run the full synthesis pipeline
subprocess.run(["python3", "-m", "codeclare.main", "--in", str(model_path)], check=True)

