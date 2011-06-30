new_history = []

open("bash_history") do |file|
  file.each do |line|
    new_history << line
  end
end

unless new_history.uniq!.nil?
  File.open("bash_history", "w") do |file|
    file.write(new_history)
  end
end