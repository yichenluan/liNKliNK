#!/usr/bin/env python
# -*- coding: utf-8 -*-

import link

urls = [
	(r"/", link.IndexHandler),
	(r"/signUp", link.SignUpHandler),
	(r"/signIn", link.SignInHandler),
	(r"/signOut", link.SignOutHandler),
	(r"/home", link.HomeHandler),
	(r"/home/(.*)", link.ShowCategoryHandler),
	(r"/news", link.ShowNewsHandler),
	(r"/people/(\d*)", link.PeopleHandler),
	(r"/people/(\d*)/follow", link.FollowHandler),
	(r"/people/(\d*)/cancleFollow", link.CancleFollowHandler),
	(r"/people/(\d*)/followers", link.ShowFollowersHandler),
	(r"/people/(\d*)/following", link.ShowFollowingHandler),
	(r"/people/(\d*)/category/(.*)", link.PeopleCategoryHandler),
	(r"/addCategory", link.AddCategoryHandler),
	(r"/addLink", link.AddLinkHandler),
	(r"/deleteCategory", link.DeleteCategoryHandler),
	(r"/deleteLink/(\d*)", link.DeleteLinkHandler),
	(r"/settings/account", link.SetAccountHandler),
	(r"/settings/password", link.SetPasswordHandler),
	(r"/settings/information", link.SetInformationHandler),
]