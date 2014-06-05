#!/usr/bin/env python
# -*- coding: utf-8 -*-

import md5
import re
import os
import datetime, time
import cgi

from settings import saedb
import sae.kvdb

import tornado.web
import tornado.database
from tornado.httpclient import AsyncHTTPClient


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        linkdb = tornado.database.Connection(
            host = saedb["host"] + ":" + saedb["port"], database = saedb["db"],
            user = saedb["user"], password = saedb["password"])
        return linkdb



    def get_current_user(self):
        email = self.get_secure_cookie("Email")
        if not email: 
            return None
        me = self.db.get("select * from Users where Email = %s", email)
        return me
       
    def getFollowInfo(self):
        followInfo = dict()
        kv = sae.kvdb.KVClient()
        selfID = str(self.current_user.ID)
        selfFollowing = selfID + 'following'
        selfFollowers = selfID + 'followers'
        selfFollowingVal = kv.get(selfFollowing)
        selfFollowersVal = kv.get(selfFollowers)
        if not selfFollowingVal:
            followInfo['following'] = 0
            followInfo['followingVal'] = []
        else:
            followInfo['following'] = len(selfFollowingVal)
            followInfo['followingVal'] = selfFollowingVal
        if not selfFollowersVal:
            followInfo['followers'] = 0
            followInfo['followersVal'] = []
        else:
            followInfo['followers'] = len(selfFollowersVal)
            followInfo['followersVal'] = selfFollowersVal
        kv.disconnect_all()
        return followInfo

class IndexHandler(BaseHandler):
    def get(self):
        if self.current_user:
            self.redirect('/home')
        else:
            self.render("index.html",me = self.current_user, message = [])

class SignUpHandler(BaseHandler):
    def post(self):
        info = dict()
        info['Name'] = self.get_argument("Name","")
        info['Email'] = self.get_argument("Email","")
        info['Password'] = self.get_argument("Password","")
        infoMessage = self.checkInfo(info)
        if infoMessage == ['ok']:
            self.addUser(info)
            self.render("index.html",me = self.current_user, message = [u"注册成功，请登录"])
        else:
            self.render("index.html",me = self.current_user, message = infoMessage)

    def checkEmail(self, email):
        emailExist = self.db.get("select * from Users where Email = %s", email)
        if emailExist:
            return [u"邮箱已注册，请直接登录"]
        formatResult = re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", email)
        if not formatResult:
            return [u"邮箱格式不正确"]
        else:
            return []

    def checkInfo(self, info):
        if not info['Name']:
            return [u"昵称不能为空"]
        if len(info['Name']) > 15:
            return [u"昵称长度超出限制"]
        message = self.checkEmail(info['Email'])
        if message != []:
            return message
        if not (len(info['Password']) >= 5 and len(info['Password']) <= 20):
            return [u"密码长度应在5到20之间"]
        return ["ok"]

    def addUser(self, info):
        userNum = len(self.db.query("select * from Users"))
        ID = 100000 + userNum
        info['Password'] = md5.new(info['Password']).hexdigest()
        self.db.execute("insert into Users (ID, Name, Email, Password) values (%s, %s, %s, %s)",
            str(ID), info['Name'], info['Email'], info['Password'])

class SignInHandler(BaseHandler):
    def post(self):
        info = dict()
        info['Email'] = self.get_argument("Email","")
        info['Password'] = self.get_argument("Password","")
        userID = self.checkUser(info)
        if userID:
            self.set_secure_cookie("Email",info['Email'])
            self.redirect('/home')
        else:
            self.render("index.html", me = self.current_user, message = [u"用户名或密码不正确"])

    def checkUser(self, info):
        user = self.db.get("select * from Users where Email = %s", info['Email'])
        if user:
            password = md5.new(info['Password']).hexdigest()
            if password == user.Password:
                return user.ID
            else:
                return False
        else:
            return False

class SignOutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("email")
        self.redirect("/")

class HomeHandler(BaseHandler):
    def get(self):
        if self.current_user:
            categoryChoose = ''
            linkList = self.db.query('select * from Links where ID = %s order by time desc',
                self.current_user.ID)
            categoryList = self.db.query("select * from Categorys where ID = %s",
                self.current_user.ID)
            badge = self.db.query('select count(*) as cateNumber from Links where ID = %s',
                self.current_user.ID)
            self.render("home.html", badge = badge, categoryChoose = categoryChoose, linkList = linkList, message = [], categoryList = categoryList, me = self.current_user)
        else:
            self.redirect("/")

class AddCategoryHandler(BaseHandler):
    def get(self):
        categoryName = self.get_argument("CategoryName","")
        message = self.checkCategory(categoryName)
        if message == ['ok']:
            self.db.execute("insert into Categorys values (%s, %s)",
                self.current_user.ID, categoryName)
            self.redirect('/home')
        else:
            categoryList = self.db.query("select * from Categorys where ID = %s",
                self.current_user.ID)
            linkList = self.db.query('select * from Links where ID = %s order by time desc',
                self.current_user.ID)
            badge = self.db.query('select count(*) as cateNumber from Links where ID = %s',
                self.current_user.ID)
            self.render("home.html", linkList = linkList, badge = badge, categoryChoose = '', message = message, categoryList = categoryList, me = self.current_user)


    def checkCategory(self, categoryName):
        if not categoryName:
            return [u'请输入类别名称']
        if len(categoryName) >19:
            return [u'类别名称过长']
        categoryExist = self.db.query("select * from Categorys where ID = %s and Category = %s",
            self.current_user.ID, categoryName)
        if categoryExist:
            return [u'类别已存在']
        return ['ok']

class AddLinkHandler(BaseHandler):
    def post(self):
        info = dict()
        info['Link'] = self.get_argument('Link','')
        info['Headline'] = self.get_argument('Headline','')
        info['Introduction'] = self.get_argument('Introduction', '')
        info['Time'] = datetime.datetime.now()
        info['Category'] = self.get_argument('Category', '')
        info['ID'] = self.current_user.ID
        #linkNum = len(self.db.query("select * from Links"))
        #info['LinkID'] = 100000 + linkNum
        linkOrder = self.db.query('select max(LinkID) as MaxLinkOrder from Links')
        if not linkOrder[0].MaxLinkOrder:
            info['LinkID'] = 100000
        else:
            info['LinkID'] = 1 + int(linkOrder[0].MaxLinkOrder)
        message = self.checkLink(info)
        if message == ['ok']:
            self.db.execute('insert into Links values (%s, %s, %s, %s, %s, %s, %s)',
                str(info['LinkID']), info['ID'], info['Link'], info['Headline'], info['Introduction'], info['Time'], info['Category'])
            self.redirect('/home')
        else:
            linkList = self.db.query('select * from Links where ID = %s order by time desc',
                self.current_user.ID)
            categoryList = self.db.query("select * from Categorys where ID = %s",
                self.current_user.ID)
            badge = self.db.query('select count(*) as cateNumber from Links where ID = %s',
                self.current_user.ID)
            self.render('home.html', badge = badge, categoryChoose = '', linkList = linkList, message = message, categoryList = categoryList, me = self.current_user)

    def checkLink(self, info):
        if not info['Link']:
            return [u'请输入链接']
        if not info['Headline']:
            return [u'请输入标题']
        if len(info['Headline']) > 99:
            return [u'标题长度超出限制']
        if len(info['Introduction']) > 249:
            return [u'简介长度超出限制']
        return ['ok']

class ShowCategoryHandler(BaseHandler):
    def get(self, input):
        categoryChoose = input
        categoryList = self.db.query('select * from Categorys where ID = %s',
            self.current_user.ID)
        linkList = self.db.query('select * from Links where ID = %s and Category = %s order by time desc',
            self.current_user.ID, categoryChoose)
        badge = self.db.query('select count(*) as cateNumber from Links where ID = %s',
            self.current_user.ID)
        self.render("home.html", badge = badge, categoryChoose = categoryChoose, linkList = linkList, message = [], categoryList = categoryList, me = self.current_user)


class DeleteCategoryHandler(BaseHandler):
    def get(self):
        categoryName = self.get_argument('Category','')
        if not categoryName:
            linkList = self.db.query('select * from Links where ID = %s order by time desc',
                self.current_user.ID)
            categoryList = self.db.query("select * from Categorys where ID = %s",
                self.current_user.ID)
            badge = self.db.query('select count(*) as cateNumber from Links where ID = %s',
                self.current_user.ID)
            self.render('home.html', badge = badge, categoryChoose = '', linkList = linkList, message = [u'请选择要删除的类别'], categoryList = categoryList, me = self.current_user)
        else:
            self.db.execute('delete from Categorys where ID = %s and Category = %s',
                self.current_user.ID, categoryName)
            self.db.execute('delete from Links where ID = %s and Category = %s',
                self.current_user.ID, categoryName)
            self.redirect('/home')
class DeleteLinkHandler(BaseHandler):
    def get(self, input):
        linkID = str(input)
        self.db.execute('delete from Links where LinkID = %s', linkID)
        self.redirect('/home')

class PeopleHandler(BaseHandler):
    def get(self, input):
        peopleID = str(input)
        people = self.db.query('select * from Users where ID = %s', peopleID)
        people = people[0]
        peopleCategoryList = self.db.query('select * from Categorys where ID = %s', peopleID)
        peopleLinkList = self.db.query('select * from Links where ID = %s order by time desc', peopleID)
        introList = self.db.query('select * from Informations where ID = %s',
            peopleID)
        if self.current_user:
            categoryList = self.db.query("select * from Categorys where ID = %s",
                self.current_user.ID)
            followInfo = dict()
            kv = sae.kvdb.KVClient()
            peopleFollowing = str(peopleID) + 'following'
            peopleFollowers = str(peopleID) + 'followers'
            selfFollowing = str(self.current_user.ID) + 'following'
            peopleFollowingVal = kv.get(peopleFollowing)
            peopleFollowersVal = kv.get(peopleFollowers)
            selfFollowingVal = kv.get(selfFollowing)
            if not peopleFollowingVal:
                followInfo['following'] = 0
            else:
                followInfo['following'] = len(peopleFollowingVal)
            if not peopleFollowersVal:
                followInfo['followers'] = 0
            else:
                followInfo['followers'] = len(peopleFollowersVal)
            if not selfFollowingVal:
                followInfo['selfFollowPeople'] = False
            else:
                if peopleID in selfFollowingVal:
                    followInfo['selfFollowPeople'] = True
                else:
                    followInfo['selfFollowPeople'] = False
            kv.disconnect_all()
            self.render('people.html', me = self.current_user, categoryList = categoryList, people = people,
                peopleCategoryList = peopleCategoryList, peopleLinkList = peopleLinkList, followInfo = followInfo, 
                introList = introList, peopleCategoryChoose = '')
        else:
            self.render('people.html', me = self.current_user, people = people,
                peopleCategoryList = peopleCategoryList, peopleLinkList = peopleLinkList, introList = introList)

class PeopleCategoryHandler(BaseHandler):
    def get(self, input, peopleCategory):
        peopleID = str(input)
        peopleCategory = peopleCategory
        people = self.db.query('select * from Users where ID = %s', peopleID)
        people = people[0]
        peopleCategoryList = self.db.query('select * from Categorys where ID = %s', peopleID)
        peopleLinkList = self.db.query('select * from Links where ID = %s and Category = %s order by time desc', 
            peopleID, peopleCategory)
        introList = self.db.query('select * from Informations where ID = %s',
            peopleID)
        if self.current_user:
            categoryList = self.db.query("select * from Categorys where ID = %s",
                self.current_user.ID)
            followInfo = dict()
            kv = sae.kvdb.KVClient()
            peopleFollowing = str(peopleID) + 'following'
            peopleFollowers = str(peopleID) + 'followers'
            selfFollowing = str(self.current_user.ID) + 'following'
            peopleFollowingVal = kv.get(peopleFollowing)
            peopleFollowersVal = kv.get(peopleFollowers)
            selfFollowingVal = kv.get(selfFollowing)
            if not peopleFollowingVal:
                followInfo['following'] = 0
            else:
                followInfo['following'] = len(peopleFollowingVal)
            if not peopleFollowersVal:
                followInfo['followers'] = 0
            else:
                followInfo['followers'] = len(peopleFollowersVal)
            if not selfFollowingVal:
                followInfo['selfFollowPeople'] = False
            else:
                if peopleID in selfFollowingVal:
                    followInfo['selfFollowPeople'] = True
                else:
                    followInfo['selfFollowPeople'] = False
            kv.disconnect_all()
            self.render('people.html', me = self.current_user, categoryList = categoryList, people = people,
                peopleCategoryList = peopleCategoryList, peopleLinkList = peopleLinkList, followInfo = followInfo, 
                introList = introList, peopleCategoryChoose = peopleCategory)
        else:
            self.render('people.html', me = self.current_user, people = people,
                peopleCategoryList = peopleCategoryList, peopleLinkList = peopleLinkList, introList = introList)

class FollowHandler(BaseHandler):
    def get(self, input):
        kv = sae.kvdb.KVClient()
        peopleID = str(input)
        selfID = str(self.current_user.ID)
        selfFollowing = selfID + 'following'
        peopleFollowers = peopleID + 'followers'
        selfFollowingVal = kv.get(selfFollowing)
        peopleFollowersVal = kv.get(peopleFollowers)
        if selfFollowingVal:
            selfFollowingVal.append(peopleID)
            kv.replace(selfFollowing, selfFollowingVal)
        else:
            selfFollowingVal = [peopleID]
            kv.set(selfFollowing, selfFollowingVal)
        if peopleFollowersVal:
            peopleFollowersVal.append(selfID)
            kv.replace(peopleFollowers, peopleFollowersVal)
        else:
            peopleFollowersVal = [selfID]
            kv.set(peopleFollowers, peopleFollowersVal)
        kv.disconnect_all()
        self.redirect('/people/' + peopleID)

class CancleFollowHandler(BaseHandler):
    def get(self, input):
        kv = sae.kvdb.KVClient()
        peopleID = str(input)
        selfID = str(self.current_user.ID)
        selfFollowing = selfID + 'following'
        peopleFollowers = peopleID + 'followers'
        selfFollowingVal = kv.get(selfFollowing)
        peopleFollowersVal = kv.get(peopleFollowers)

        selfFollowingVal.remove(peopleID)
        peopleFollowersVal.remove(selfID)

        kv.set(selfFollowing, selfFollowingVal)
        kv.set(peopleFollowers, peopleFollowersVal)

        kv.disconnect_all()

        self.redirect('/people/' + peopleID)

class SetAccountHandler(BaseHandler):
    def get(self):
        followInfo = BaseHandler.getFollowInfo(self)
        categoryList = self.db.query("select * from Categorys where ID = %s",
            self.current_user.ID)
        introList = self.db.query('select * from Informations where ID = %s',
            self.current_user.ID)
        self.render('accountSetting.html', me = self.current_user, followInfo = followInfo, 
            categoryList = categoryList, introList = introList, message = [])

    def post(self):
        accountInfo = dict()
        accountInfo['nameChanged'] = self.get_argument('nameChanged','')
        accountInfo['emailChanged'] = self.get_argument('emailChanged','')
        pwd = self.get_argument('password','')
        accountInfo['password'] = md5.new(pwd).hexdigest()
        if accountInfo['password'] == self.current_user.Password:
            if accountInfo['nameChanged'] != self.current_user.Name:
                self.db.execute('update Users set Name = %s where ID = %s',
                    accountInfo['nameChanged'], self.current_user.ID)
            if accountInfo['emailChanged'] != self.current_user.Email:
                self.db.execute('update Users set Email = %s where ID = %s',
                    accountInfo['emailChanged'], self.current_user.ID)
            message = [u'修改成功']
        else:
            message = [u'密码错误']
        followInfo = self.getFollowInfo()
        categoryList = self.db.query("select * from Categorys where ID = %s",
            self.current_user.ID)
        introList = self.db.query('select * from Informations where ID = %s',
            self.current_user.ID)
        self.render('accountSetting.html', me = self.current_user, followInfo = followInfo, 
            categoryList = categoryList, introList = introList, message = message)



class SetPasswordHandler(BaseHandler):
    def get(self):
        followInfo = BaseHandler.getFollowInfo(self)
        categoryList = self.db.query("select * from Categorys where ID = %s",
            self.current_user.ID)
        introList = self.db.query('select * from Informations where ID = %s',
            self.current_user.ID)
        self.render('passwordSetting.html', me = self.current_user, followInfo = followInfo, 
            categoryList = categoryList, introList = introList, message = [])       

    def post(self):
        currentPwd = self.get_argument('currentPassword','')
        newPwd = self.get_argument('newPassword', '')
        currentPassword = md5.new(currentPwd).hexdigest()
        newPassword = md5.new(newPwd).hexdigest()
        if currentPassword == self.current_user.Password:
            self.db.execute('update Users set Password = %s where ID = %s',
                newPassword, self.current_user.ID)
            message = [u'修改成功']
        else:
            message = [u'当前密码错误']
        followInfo = self.getFollowInfo()
        categoryList = self.db.query("select * from Categorys where ID = %s",
            self.current_user.ID)
        introList = self.db.query('select * from Informations where ID = %s',
            self.current_user.ID)
        self.render('passwordSetting.html', me = self.current_user, followInfo = followInfo, 
            categoryList = categoryList, introList = introList, message = message)



class SetInformationHandler(BaseHandler):
    def get(self):
        followInfo = BaseHandler.getFollowInfo(self)
        categoryList = self.db.query("select * from Categorys where ID = %s",
            self.current_user.ID)
        introList = self.db.query('select * from Informations where ID = %s',
            self.current_user.ID)
        self.render('infoSetting.html', me = self.current_user, followInfo = followInfo, 
            categoryList = categoryList, introList = introList, message = [])       

    def post(self):
        currentPwd = self.get_argument('password', '')
        currentPassword = md5.new(currentPwd).hexdigest()
        introduce = self.get_argument('introduce', '')
        if currentPassword == self.current_user.Password:
            currentIntro = self.db.query('select * from Informations where ID = %s', self.current_user.ID)
            if currentIntro:
                self.db.execute('update Informations set Intro = %s where ID = %s',
                    introduce, self.current_user.ID)
            else:
                self.db.execute('insert into Informations values (%s, %s)',
                    self.current_user.ID, introduce)
            message = [u'修改成功']
        else:
            message = [u'当前密码错误']
        followInfo = self.getFollowInfo()
        categoryList = self.db.query("select * from Categorys where ID = %s",
            self.current_user.ID)
        introList = self.db.query('select * from Informations where ID = %s',
            self.current_user.ID)
        self.render('infoSetting.html', me = self.current_user, followInfo = followInfo, 
            categoryList = categoryList, introList = introList, message = message)      


class ShowFollowersHandler(BaseHandler):
    def get(self, input):
        peopleID = str(input)
        people = self.db.query('select * from Users where ID = %s', peopleID)
        people = people[0]
        introList = self.db.query('select * from Informations where ID = %s',
            peopleID)
        categoryList = self.db.query('select * from Categorys where ID = %s',
            self.current_user.ID)
        followInfo = dict()
        kv = sae.kvdb.KVClient()
        peopleFollowing = str(peopleID) + 'following'
        peopleFollowers = str(peopleID) + 'followers'
        selfFollowing = str(self.current_user.ID) + 'following'
        selfFollowers = str(self.current_user.ID) + 'followers'
        peopleFollowingVal = kv.get(peopleFollowing)
        peopleFollowersVal = kv.get(peopleFollowers)
        selfFollowingVal = kv.get(selfFollowing)
        selfFollowersVal = kv.get(selfFollowers)
        if not peopleFollowingVal:
            followInfo['following'] = 0
            peopleFollowingVal = []
        else:
            followInfo['following'] = len(peopleFollowingVal)
        if not peopleFollowersVal:
            followInfo['followers'] = 0
            peopleFollowersVal = []
        else:
            followInfo['followers'] = len(peopleFollowersVal)
        if not selfFollowingVal:
            followInfo['selfFollowPeople'] = False
        else:
            if peopleID in selfFollowingVal:
                followInfo['selfFollowPeople'] = True
            else:
                followInfo['selfFollowPeople'] = False
        if not selfFollowersVal:
            followInfo['selfFollowersNumber'] = 0
        else:
            followInfo['selfFollowersNumber'] = len(selfFollowersVal)
        peopleFollowersInfo = dict()
        peopleFollowersList = []
        for peopleFollowersID in peopleFollowersVal:
            Followers = self.db.query('select * from Users where ID = %s', peopleFollowersID)
            Followers = Followers[0]
            peopleFollowersInfo['Name'] = Followers.Name
            peopleFollowersInfo['ID'] = Followers.ID
            FollowersIntroList = self.db.query('select * from Informations where ID = %s', peopleFollowersID)
            peopleFollowersInfo['IntroList'] = FollowersIntroList
            FollowersFollowers = str(peopleFollowersID) + 'followers'
            FollowersFollowersVal = kv.get(FollowersFollowers)
            if not FollowersFollowersVal:
                peopleFollowersInfo['Followers'] = 0
            else:
                peopleFollowersInfo['Followers'] = len(FollowersFollowersVal)
            FollowersCategoryNumber = self.db.query('select count(*) as cateNumber from Categorys where ID = %s',
                peopleFollowersID)
            peopleFollowersInfo['CategoryNumber'] = FollowersCategoryNumber[0]
            FollowersLinkNumber = self.db.query('select count(*) as linkNumber from Links where ID = %s',
                peopleFollowersID)
            peopleFollowersInfo['LinkNumber'] = FollowersLinkNumber[0]
            if not selfFollowingVal:
                peopleFollowersInfo['SelfFollowPeople'] = False
            else:
                if peopleFollowersID in selfFollowingVal:
                    peopleFollowersInfo['SelfFollowPeople'] = True
                else:
                    peopleFollowersInfo['SelfFollowPeople'] = False
            peopleFollowersList.append(peopleFollowersInfo)
            peopleFollowersInfo = dict()
        self.render('followers.html', me = self.current_user, categoryList = categoryList, people = people,
            followInfo = followInfo, introList = introList, peopleFollowersList = peopleFollowersList)


class ShowFollowingHandler(BaseHandler):
    def get(self, input):
        peopleID = str(input)
        people = self.db.query('select * from Users where ID = %s', peopleID)
        people = people[0]
        introList = self.db.query('select * from Informations where ID = %s',
            peopleID)
        categoryList = self.db.query('select * from Categorys where ID = %s',
            self.current_user.ID)
        followInfo = dict()
        kv = sae.kvdb.KVClient()
        peopleFollowing = str(peopleID) + 'following'
        peopleFollowers = str(peopleID) + 'followers'
        selfFollowing = str(self.current_user.ID) + 'following'
        selfFollowers = str(self.current_user.ID) + 'followers'
        peopleFollowingVal = kv.get(peopleFollowing)
        peopleFollowersVal = kv.get(peopleFollowers)
        selfFollowingVal = kv.get(selfFollowing)
        selfFollowersVal = kv.get(selfFollowers)
        if not peopleFollowingVal:
            followInfo['following'] = 0
            peopleFollowingVal = []
        else:
            followInfo['following'] = len(peopleFollowingVal)
        if not peopleFollowersVal:
            followInfo['followers'] = 0
            peopleFollowersVal = []
        else:
            followInfo['followers'] = len(peopleFollowersVal)
        if not selfFollowingVal:
            followInfo['selfFollowPeople'] = False
        else:
            if peopleID in selfFollowingVal:
                followInfo['selfFollowPeople'] = True
            else:
                followInfo['selfFollowPeople'] = False
        if not selfFollowersVal:
            followInfo['selfFollowersNumber'] = 0
        else:
            followInfo['selfFollowersNumber'] = len(selfFollowersVal)
        peopleFollowingInfo = dict()
        peopleFollowingList = []
        for peopleFollowingID in peopleFollowingVal:
            Following = self.db.query('select * from Users where ID = %s', peopleFollowingID)
            Following = Following[0]
            peopleFollowingInfo['Name'] = Following.Name
            peopleFollowingInfo['ID'] = Following.ID
            FollowingIntroList = self.db.query('select * from Informations where ID = %s', peopleFollowingID)
            peopleFollowingInfo['IntroList'] = FollowingIntroList
            FollowingFollowers = str(peopleFollowingID) + 'followers'
            FollowingFollowersVal = kv.get(FollowingFollowers)
            if not FollowingFollowersVal:
                peopleFollowingInfo['Followers'] = 0
            else:
                peopleFollowingInfo['Followers'] = len(FollowingFollowersVal)
            FollowingCategoryNumber = self.db.query('select count(*) as cateNumber from Categorys where ID = %s',
                peopleFollowingID)
            peopleFollowingInfo['CategoryNumber'] = FollowingCategoryNumber[0]
            FollowingLinkNumber = self.db.query('select count(*) as linkNumber from Links where ID = %s',
                peopleFollowingID)
            peopleFollowingInfo['LinkNumber'] = FollowingLinkNumber[0]
            if not selfFollowingVal:
                peopleFollowingInfo['SelfFollowPeople'] = False
            else:
                if peopleFollowingID in selfFollowingVal:
                    peopleFollowingInfo['SelfFollowPeople'] = True
                else:
                    peopleFollowingInfo['SelfFollowPeople'] = False
            peopleFollowingList.append(peopleFollowingInfo)
            peopleFollowingInfo = dict()
        self.render('following.html', me = self.current_user, categoryList = categoryList, people = people,
            followInfo = followInfo, introList = introList, peopleFollowingList = peopleFollowingList)


class ShowNewsHandler(BaseHandler):
    def get(self):
        categoryChoose = ''
        followInfo = BaseHandler.getFollowInfo(self)
        categoryList = self.db.query("select * from Categorys where ID = %s",
            self.current_user.ID)
        badge = self.db.query('select count(*) as cateNumber from Links where ID = %s',
            self.current_user.ID)
        newsName = dict()
        for followingID in followInfo['followingVal']:
            followingName = self.db.query('select * from Users where ID = %s', followingID)
            newsName[followingID] = followingName[0].Name
        if len(followInfo['followingVal']) == 0:
            linkList = []
        elif len(followInfo['followingVal']) == 1:
            linkList = self.db.query('select * from Links where ID = %s', followInfo['followingVal'][0])
        else:
            followingTuple = tuple(followInfo['followingVal'])
            linkList = self.db.query('select * from Links where ID in ' + str(followingTuple) + ' order by time desc limit 5')
        self.render("news.html", newsName = newsName, badge = badge, categoryChoose = categoryChoose, linkList = linkList, message = [], categoryList = categoryList, me = self.current_user)
       















