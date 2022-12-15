from math import sqrt, floor, ceil
import matplotlib.pyplot as plt


S = 3.3/.0005
H = 100.0-2
L = 76.0+8
# h=.16

wpos = []
wneg = []
Nlist = []
Haxis =[]

stepsize = .001
min_h=.16
max_h=.4
steps = floor((max_h-min_h)/stepsize)

for delta in range(0, steps):
	h= .16+delta*stepsize

	Haxis.append(h)

	a = S
	b = (h*S)+(2*h)
	c = -1*((h*H)+(2*h*L)+(H*L))

	# print(f'a {a} b {b} c {c}')

	try:
		pos_root=(-b+sqrt(b**2-4*a*c))/(2*a)
	except ValueError:
		pass
	wpos.append(pos_root)

	N = (H-2*pos_root)/(2*pos_root+2*h)
	Htot = 2*pos_root + N * (2*pos_root+2*h)
	# print(f"N: {N}, Htot: {Htot}")
	try:
		wneg.append((-b-sqrt(b**2-4*a*c))/(2*a))
	except ValueError:
		pass
	Nlist.append(N)


Hpruned = []
Npruned = []
Wpruned = []

for x, y, z in zip(Haxis,Nlist, wpos):
	if(y%1<.01):
		Hpruned.append(x)
		Npruned.append(y)
		Wpruned.append(z)

fig, ax1 = plt.subplots()
ax2 = ax1.twinx()

ax1.plot(Haxis,wpos, color = 'k')
ax2.scatter(Hpruned,Npruned, color = 'r')
ax2.set_ylim(min(Nlist)-.15,max(Nlist)+.15)
ax2.set_xlim(min(Haxis),max(Haxis))
plt.suptitle("Track width and Pattern Count")
ax1.set_xlabel("Track spacing, mm")
ax1.set_ylabel("track width, mm")
ax2.set_ylabel("Pattern count")
plt.show()

for x,y,z in zip(Hpruned,Npruned,Wpruned):
	print(f"w width {z}, h spacing {x}, N repeats {y}")

