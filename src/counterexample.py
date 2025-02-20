import numpy as np
from extrema_estimates import black_box
from z3 import *

def validateCE(model, sess):
  input_name = sess.get_inputs()[0].name
  label_name = sess.get_outputs()[0].name
  # reshape if needed
  input_shape = [dim if isinstance(dim, int) else 1 for dim in sess.get_inputs()[0].shape]
  
  x_decls = sorted([str(d) for d in model.decls() if "X_" in d.name()])
  y_decls = sorted([str(d) for d in model.decls() if "Y_" in d.name()])
  input_array = [float(model.eval(Real(d)).as_decimal(20)) for d in x_decls]
  
  output_array_pred = [float(model.eval(Real(d)).as_decimal(20)) for d in y_decls]
  output_array_true = black_box(sess, input_array, input_name, label_name, input_shape)

  if np.allclose(output_array_pred, output_array_true, rtol=0, atol=1e-15):
    return True
  return False

def enumerateCE(solver, sess):
  if str(solver.check()) == "unsat":
    return "holds"
  model = solver.model()
  variables = sorted([str(d) for d in model.decls()])
  numCEs = 0
  while str(solver.check()) == "sat" and numCEs < 10**3: # early stopping at 10^3 spurious CEs
    model = solver.model()
    numCEs += 1
    # Validate the counterexample
    if validateCE(model, sess):
      s = "violated\nCE: "
      for i in range(len(variables)):
        val = float(model.eval(Real(variables[i])).as_decimal(20))
        s += variables[i] + " = " + str(val) + "\n"
      print(f"Number of Abstract CEs explored: {numCEs}")
      return s
    # Exclude this counterexample from further consideration
    solver.add(Or([Real(v) != float(model.eval(Real(v)).as_decimal(20)) for v in variables]))
  return "unknown"
