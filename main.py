from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from datetime import date
from datetime import timedelta
import fire
import calendar
import time
from terminaltables import AsciiTable
import tinyurl

pollForWebpageReadinessWaitSeconds = 5
debug = False

class CampsiteBooker:
    def __init__(self):
        if not debug:
            options = webdriver.ChromeOptions()
            options.binary_location = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            options.add_argument('headless')
            options.add_argument('window-size=1200x600')
            self.__driver = webdriver.Chrome(chrome_options=options)
        else:
            self.__driver = webdriver.Chrome()

        self.__tableData = [["START DATE","END DATE","SITE NAME","SITE TYPE", "MAX # PEOPLE", "DRIVEWAY LENGTH", "BOOKING URL"]]
        self.__choice = 0
        self.__bunkURLS = []

    def resetTableData(self):
        self.__tableData = [["START DATE","END DATE","SITE NAME","SITE TYPE", "MAX # PEOPLE", "DRIVEWAY LENGTH", "BOOKING URL"]]
        self.__bunkURLS = []

    def getChoice(self):
        if self.__choice == 0:
            self.__choice = int(raw_input("What choice would you like to select?\n"))
            if self.__choice < 1 or self.__choice > 5:
                print "Must choose option from 1-5"
                raise SystemExit
            return self.__choice
        else:
            return self.__choice

    def CheckForFeedbackAd(self):
        #Wait to see if ad is present
        try:
            element_present = EC.presence_of_element_located((By.ID, 'acsMainInvite'))
            WebDriverWait(self.__driver, 2).until(element_present)
        except TimeoutException:
            return

        #If ad is present, click close button
        closeButton = self.__driver.find_element_by_id("acsMainInvite").find_element_by_class_name("acsAbandonButton")
        closeButton.click()
        return

    def PrintTable(self):
        table = AsciiTable(self.__tableData)
        print table.table
        self.resetTableData()

    def GetAvailableListings(self, campsiteURL, startDate, endDate, occupants, desiredNightsStayed):
        self.__driver.get(campsiteURL)

        #Doing date conversion
        months = ["Jan", "Feb", "Mar"," Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        startDateParts = startDate.split("/")
        endDateParts = endDate.split("/")
        startDate = date(int(startDateParts[2]), int(startDateParts[0]),int(startDateParts[1]))
        endDate = date(int(endDateParts[2]), int(endDateParts[0]),int(endDateParts[1]))

        startDateActual = "%s %s %d %d" % (calendar.day_name[startDate.weekday()][:3], months[startDate.month-1], startDate.day, startDate.year)
        endDateActual = "%s %s %d %d" % (calendar.day_name[endDate.weekday()][:3], months[endDate.month-1], endDate.day, endDate.year)

        #Inputting results into form
        if len(self.__driver.find_elements_by_id("mainUnifSearch")) < 1:
            return False

        #Do departure date first and then arrival date else recreation.gov will default end date to start date + 1
        self.__driver.find_element_by_id("departureDate").send_keys(endDateActual)
        self.__driver.find_element_by_id("arrivalDate").send_keys(startDateActual)
        self.__driver.find_element_by_id("camping_common_3012").send_keys(occupants)
        self.__driver.find_element_by_id("filter").click()
        #Getting all available campsites
        self.CheckForFeedbackAd()

        try:
            element_present = EC.presence_of_element_located((By.ID, 'shoppingitems'))
            WebDriverWait(self.__driver, 1).until(element_present)
        except TimeoutException:
            try:
                self.CheckForFeedbackAd()
                if len(self.__driver.find_elements_by_id("shoppingitems")) < 1 and campsiteURL not in self.__bunkURLS:
                    print "No Campsite Listings For Facility %s" % (self.__driver.find_element_by_id("cgroundName").text)
                    self.__bunkURLS.append(campsiteURL)
                    return False
            except TimeoutException:
                if campsiteURL not in self.__bunkURLS:
                    print "Couldn't grab site listings for this campsite %s" % (campsiteURL)
                    self.__bunkURLS.append(campsiteURL)
                return False

        try:
            allListings = self.__driver.find_element_by_id('shoppingitems').find_element_by_tag_name("tbody").find_elements_by_tag_name("tr")
        except:
            return False

        for listing in allListings:
            cells = listing.find_elements_by_tag_name("td")
            if len(cells) == 7:
                if "available" in cells[6].text and "not available" not in cells[6].text:
                    realUrl = tinyurl.create_one(('%s & arvdate= %s & lengthOfStay = %d' % (cells[6].find_element_by_tag_name("a").get_attribute("href"),startDate,desiredNightsStayed)).replace(" ",""))
                    self.__tableData.append([startDate, endDate, self.__driver.find_element_by_id("cgroundName").text, cells[2].text, cells[3].text,cells[4].text,realUrl])

        return True

    def searchForMultiNightCampSite(self, searchTerm, occupants, startDate, desiredNightsStayed, printTable):
        startDateParts = startDate.split("/")
        startDateTime = date(int(startDateParts[2]), int(startDateParts[0]), int(startDateParts[1]))
        endDate = startDateTime + timedelta(days=desiredNightsStayed)
        endDateActual = "%.2d/%.2d/%.2d" % (endDate.month, endDate.day, endDate.year)

        #Homepage navigation
        self.__driver.get("https://www.recreation.gov/unifSearch.do")
        if not self.pollForWebpageReadiness("https://www.recreation.gov/unifSearch.do",pollForWebpageReadinessWaitSeconds):
            return self.searchForMultiNightCampSite(searchTerm, occupants, startDate, desiredNightsStayed, printTable)

        homePageSearchBar = self.__driver.find_element_by_id("locationCriteria")
        homePageSearchBar.clear()
        homePageSearchBar.send_keys(searchTerm)
        homePageSearchBar.send_keys(Keys.RETURN)

        #Wait until DOM is loaded then find all suggested places
        for i in range(0,2):
            try:
                element_present = EC.presence_of_element_located((By.ID, 'suggested_places_content'))
                WebDriverWait(self.__driver, 5).until (element_present)
            except TimeoutException:
                print "Timed out waiting for page to load"
                raise SystemExit
            time.sleep(2)

        #Prompt user for choice of selected places
        parkSuggestionList = self.__driver.find_element_by_id("suggested_places_content")
        parkSuggestions = parkSuggestionList.find_elements_by_class_name("suggested_place")

        if self.__choice == 0:
            for num, response in enumerate(parkSuggestions[:5]):
                print str(num + 1) + ": " + response.text

        self.getChoice()

        chosenOption = parkSuggestions[self.getChoice()-1]
        chosenOption.click()

        #Check to see if ad pops up
        campgroundSites = self.__driver.find_element_by_id("FacSectionRIDB").find_elements_by_tag_name('a')

        tableData = []
        campsiteURLs = []
        for campsite in campgroundSites:
            campsiteURLs.append(campsite.get_attribute("href"))

        #this is baller asss code
        for campsiteURL in campsiteURLs:
            self.GetAvailableListings(campsiteURL, startDate, endDateActual, occupants, desiredNightsStayed)

        if printTable:
            self.PrintTable()

    def searchForCampsiteOverDateRange(self, searchTerm, occupants, startDateRange, endDateRange, desiredNightsStayed):
        startDateParts = startDateRange.split("/")
        endDateParts = endDateRange.split("/")
        startDate = date(int(startDateParts[2]), int(startDateParts[0]), int(startDateParts[1]))
        endDate = date(int(endDateParts[2]), int(endDateParts[0]), int(endDateParts[1]))

        if endDate < startDate:
            print "End Date is before start date!"
            raise SystemExit

        tempDate = startDate
        while tempDate != endDate:
            startDateActual = "%.2d/%.2d/%.2d" % (tempDate.month, tempDate.day, tempDate.year)
            self.searchForMultiNightCampSite(searchTerm, occupants, startDateActual, desiredNightsStayed, False)
            tempDate = tempDate + timedelta(days=1)

        headerMessage = ("\nCampsites in %s available from %s to %s for %d nights for %d people or greater" % (searchTerm, startDateRange, endDateRange, desiredNightsStayed, occupants)).upper()
        print headerMessage
        self.PrintTable()

    def pollForWebpageReadiness(self, url, seconds):
        try:
            self.__driver.get(url)
            element_present = EC.presence_of_element_located((By.ID, 'headerGraphic'))
            WebDriverWait(self.__driver, seconds).until(element_present)
        except:
            print "Webpage %s is not available -- Timeout %d seconds" % (url, seconds)
            return False
        return True

    def __del__(self):
        if not debug:
            self.__driver.close()

class FireWrapper:
    def bookSingleNight(self,SearchTerm,StartDate,NumOccupants):
        booker = CampsiteBooker()
        return booker.searchForMultiNightCampSite(SearchTerm,NumOccupants,StartDate,1,True)
    def bookNightsOverRange(self,SearchTerm,StartDate,EndDate,DesiredNightsStayed,NumOccupants):
        booker = CampsiteBooker()
        return booker.searchForCampsiteOverDateRange(SearchTerm,NumOccupants,StartDate,EndDate,DesiredNightsStayed)

if __name__ == "__main__":
    fire.Fire(FireWrapper)