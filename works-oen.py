def getMaximumTeamSize(startTime, endTime):
    single_list=[]
    
    n = len(startTime)
    if not (1 <= n <= 2 * 10**5):
        return 0
    
    for i in range(n):
        if startTime[i] <= endTime[i] and 1 <= startTime[i] and endTime[i] <= 10**9:
                single_list.append([startTime[i],endTime[i]])

    print(single_list)
    max_team_size=0
    for i in single_list:
        team_size=0
        for j in single_list:
            if i[0] <= j[1] and i[1] >= j[0]:
                team_size+=1
        if team_size>max_team_size:
            max_team_size=team_size
    return max_team_size
