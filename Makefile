bump:
	- hatch run cov
	- hatch version patch
	- hatch build
	- hatch publish
	- hatch clean
	- git add .
	- git commit -m "Bump version"
