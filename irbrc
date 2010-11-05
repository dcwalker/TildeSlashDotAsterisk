require 'rubygems'
require 'pp'
begin
  require 'wirble'

  # init wirble
  Wirble.init
  Wirble.colorize
rescue LoadError => err
  $stderr.puts "Couldn't load Wirble: #{err}"
end