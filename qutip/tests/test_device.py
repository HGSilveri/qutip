import numpy as np
import pytest
import qutip
from qutip.qip.circuit import Gate
from qutip.qip.operations.gates import gate_sequence_product
from qutip.qip.device.cavityqed import DispersiveCavityQED
from qutip.qip.device.spinchain import LinearSpinChain, CircularSpinChain


_tol = 1e-2

_x = Gate("X", targets=[0])
_z = Gate("Z", targets=[0])
_y = Gate("Y", targets=[0])
_snot = Gate("SNOT", targets=[0])
_rz = Gate("RZ", targets=[0], arg_value=np.pi/2, arg_label=r"\pi/2")
_rx = Gate("RX", targets=[0], arg_value=np.pi/2, arg_label=r"\pi/2")
_ry = Gate("RY", targets=[0], arg_value=np.pi/2, arg_label=r"\pi/2")
_iswap = Gate("ISWAP", targets=[0, 1])
_cnot = Gate("CNOT", targets=[0], controls=[1])
_sqrt_iswap = Gate("SQRTISWAP", targets=[0, 1])


single_gate_tests = [
    pytest.param(2, [_z], id="Z"),
    pytest.param(2, [_x], id="X"),
    pytest.param(2, [_y], id="Y"),
    pytest.param(2, [_snot], id="SNOT"),
    pytest.param(2, [_rz], id="RZ"),
    pytest.param(2, [_rx], id="RX"),
    pytest.param(2, [_ry], id="RY"),
    pytest.param(2, [_iswap], id="ISWAP"),
    pytest.param(2, [_sqrt_iswap], id="SQRTISWAP", marks=pytest.mark.skip),
    pytest.param(2, [_cnot], id="CNOT"),
]


device_lists = [
    pytest.param(DispersiveCavityQED, {"g": 0.02}, id="DispersiveCavityQED"),
    pytest.param(LinearSpinChain, {}, id = "LinearSpinChain"),
    pytest.param(CircularSpinChain, {}, id = "CircularSpinChain"),
]

@pytest.mark.parametrize(("num_qubits", "gates"), single_gate_tests)
@pytest.mark.parametrize(("device_class", "kwargs"), device_lists)
def test_device_against_gate_sequence(
    num_qubits, gates, device_class, kwargs):
    circuit = qutip.qip.circuit.QubitCircuit(num_qubits)
    for gate in gates:
        circuit.add_gate(gate)
    U_ideal = gate_sequence_product(circuit.propagators())

    device = device_class(num_qubits, correct_global_phase=True)
    U_physical = gate_sequence_product(device.run(circuit))
    assert (U_ideal - U_physical).norm() < _tol


@pytest.mark.parametrize(("num_qubits", "gates"), single_gate_tests)
@pytest.mark.parametrize(("device_class", "kwargs"), device_lists)
def test_analytical_evolution(num_qubits, gates, device_class, kwargs):
    circuit = qutip.qip.circuit.QubitCircuit(num_qubits)
    for gate in gates:
        circuit.add_gate(gate)
    state = qutip.rand_ket(2**num_qubits)
    state.dims = [[2]*num_qubits, [1]*num_qubits]
    ideal = gate_sequence_product([state] + circuit.propagators())
    device = device_class(num_qubits, correct_global_phase=True)
    operators = device.run_state(init_state=state, qc=circuit, analytical=True)
    result = gate_sequence_product(operators)
    assert abs(qutip.metrics.fidelity(result, ideal) - 1) < _tol


@pytest.mark.parametrize(("num_qubits", "gates"), single_gate_tests)
@pytest.mark.parametrize(("device_class", "kwargs"), device_lists)
def test_numerical_evolution(
    num_qubits, gates, device_class, kwargs):
    num_qubits = 3
    circuit = qutip.qip.circuit.QubitCircuit(num_qubits)
    for gate in gates:
        circuit.add_gate(gate)
    device = device_class(num_qubits, **kwargs)
    device.load_circuit(circuit)

    state = qutip.rand_ket(2**num_qubits)
    state.dims = [[2]*num_qubits, [1]*num_qubits]
    target = gate_sequence_product([state] + circuit.propagators())
    if len(device.dims) > num_qubits:
        num_ancilla = len(device.dims)-num_qubits
        ancilla_indices = slice(0, num_ancilla)
        extra = qutip.basis(device.dims[ancilla_indices], [0]*num_ancilla)
        init_state = qutip.tensor(extra, state)
    else:
        init_state = state
    options = qutip.Options(store_final_state=True, nsteps=50_000)
    result = device.run_state(init_state=init_state,
                              analytical=False,
                              options=options)
    if len(device.dims) > num_qubits:
        target = qutip.tensor(extra, target)
    assert _tol > abs(1 - qutip.metrics.fidelity(result.final_state, target))


circuit = qutip.qip.circuit.QubitCircuit(3)
circuit.add_gate("RX", targets=[0], arg_value=np.pi/2)
circuit.add_gate("RZ", targets=[2], arg_value=np.pi)
circuit.add_gate("CNOT", targets=[0], controls=[1])
circuit.add_gate("ISWAP", targets=[2, 1])
circuit.add_gate("Y", targets=[2])
circuit.add_gate("Z", targets=[0])
circuit.add_gate("CNOT", targets=[0], controls=[2])
circuit.add_gate("Z", targets=[1])
circuit.add_gate("X", targets=[1])

from copy import deepcopy
circuit2 = deepcopy(circuit)
circuit2.add_gate("SQRTISWAP", targets=[0, 2])  # supported only by SpinChain


@pytest.mark.parametrize(("circuit", "device_class", "kwargs"), [
    pytest.param(circuit, DispersiveCavityQED, {"g": 0.02},
                 id="DispersiveCavityQED"),
    pytest.param(circuit2, LinearSpinChain, {}, id = "LinearSpinChain"),
    pytest.param(circuit2, CircularSpinChain, {}, id = "CircularSpinChain"),
])
@pytest.mark.parametrize(("schedule_mode"), ["ASAP", "ALAP", None])
def test_numerical_circuit(circuit, device_class, kwargs, schedule_mode):
    num_qubits = circuit.N
    device = device_class(circuit.N, **kwargs)
    device.load_circuit(circuit, schedule_mode=schedule_mode)

    state = qutip.rand_ket(2**num_qubits)
    state.dims = [[2]*num_qubits, [1]*num_qubits]
    target = gate_sequence_product([state] + circuit.propagators())
    if len(device.dims) > num_qubits:
        num_ancilla = len(device.dims)-num_qubits
        ancilla_indices = slice(0, num_ancilla)
        extra = qutip.basis(device.dims[ancilla_indices], [0]*num_ancilla)
        init_state = qutip.tensor(extra, state)
    else:
        init_state = state
    options = qutip.Options(store_final_state=True, nsteps=50_000)
    result = device.run_state(init_state=init_state,
                              analytical=False,
                              options=options)
    if len(device.dims) > num_qubits:
        target = qutip.tensor(extra, target)
    assert _tol > abs(1 - qutip.metrics.fidelity(result.final_state, target))
