import numpy as np
import matplotlib.pyplot as plt

# Demand and supply functions
Q = np.linspace(0, 10, 100)

# Original curves
P_d = 12 - Q        # demand
P_s = 2 + Q         # supply

# Right shift demand (increased demand)
P_d_right = 14 - Q

# Left shift demand (decreased demand)
P_d_left = 10 - Q

# Right shift supply (increased supply)
P_s_right = 1 + Q

# Left shift supply (decreased supply)
P_s_left = 3 + Q

plt.figure()

# Plot original
plt.plot(Q, P_d, label="Demand")
plt.plot(Q, P_s, label="Supply")

# Plot shifts
plt.plot(Q, P_d_right, linestyle="--", label="Demand Shift Right")
plt.plot(Q, P_d_left, linestyle="--", label="Demand Shift Left")
plt.plot(Q, P_s_right, linestyle=":", label="Supply Shift Right")
plt.plot(Q, P_s_left, linestyle=":", label="Supply Shift Left")

plt.xlabel("Quantity")
plt.ylabel("Price")
plt.title("Shifts in Demand and Supply")
plt.legend()
plt.grid()
plt.show()
