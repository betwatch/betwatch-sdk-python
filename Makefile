patch-publish:
	- hatch clean
	- hatch version patch
	- hatch build
	- hatch publish
